from app.domain.clearing import ClearingBatch
from app.support.types import checked,money,batch_snapshot,ensure_unassigned,total_money,BatchSnapshot
from app.support.errors import DomainError


class ClearingService:
    def __init__(self,repository,rules=()):
        self._repository=repository
        self._rules=tuple(rules)

    def create_batch(self,batch_id,currency):
        batch=self._repository.add(ClearingBatch(batch_id,currency))
        return batch_snapshot(batch)

    def get_batch(self,batch_id):
        return batch_snapshot(self._repository.get(batch_id))

    def add(self,batch_id,tx):
        batch=self._repository.get(batch_id)
        batch.validate_add(tx)
        ensure_unassigned(self._repository,tx.transaction_id)
        if batch.transaction_count+1>3:raise DomainError("BATCH_COUNT_LIMIT")
        if batch.total().add(tx.amount).amount>100:raise DomainError("BATCH_AMOUNT_LIMIT")
        batch.add_transaction(tx)
        return self.get_batch(batch_id)

    def close(self,batch_id):
        self._repository.get(batch_id).close()
        return self.get_batch(batch_id)

def make_entity(*args, **kwargs):
    return ClearingBatch(*args, **kwargs)


def invoke(service, method, *args, **kwargs):
    return getattr(service, method)(*args, **kwargs)


def view(entity):
    return {'batch_id': entity.batch_id, 'currency': entity.currency, 'status': entity.status, 'transactions': entity.transactions}


from app.support.types import Repository,money

def new_service(repository=None):
    return ClearingService(repository if repository is not None else Repository("batch_id","DUPLICATE_BATCH"))
