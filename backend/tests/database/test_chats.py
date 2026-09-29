import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.database.chats import ChatRepository, ThreadForbiddenError


class Query:
    def __init__(self, data):
        self.data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    async def execute(self):
        return SimpleNamespace(data=self.data)


class Client:
    def __init__(self, *, table_data=None):
        self.table_data = table_data or []
        self.rpc_call = None

    def table(self, name):
        return Query(self.table_data)

    def rpc(self, name, params):
        self.rpc_call = (name, params)
        return Query([])


def test_require_thread_rejects_another_owner():
    current_user_id = str(uuid4())
    repository = ChatRepository(
        user_id=current_user_id,
        user_client=Client(),
        service_client=Client(table_data=[{"user_id": str(uuid4())}]),
    )

    try:
        asyncio.run(repository.require_thread(uuid4()))
    except ThreadForbiddenError:
        pass
    else:
        raise AssertionError("Expected access to another user's thread to fail")


def test_persist_turn_calls_atomic_rpc():
    client = Client()
    repository = ChatRepository(
        user_id=str(uuid4()),
        user_client=client,
        service_client=Client(),
    )
    thread_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()

    asyncio.run(
        repository.persist_turn(
            thread_id=thread_id,
            user_message_id=user_message_id,
            user_content="Question",
            user_parts=[{"type": "text", "text": "Question"}],
            assistant_message_id=assistant_message_id,
            assistant_content="Answer",
            assistant_parts=[{"type": "text", "text": "Answer"}],
            assistant_usage={"input_tokens": 10, "output_tokens": 5},
            citations=[
                {
                    "document_id": str(uuid4()),
                    "chunk_id": str(uuid4()),
                    "position": 1,
                    "quoted_text": "Evidence",
                    "page": 2,
                    "section": "Results",
                }
            ],
        )
    )

    name, params = client.rpc_call
    assert name == "persist_chat_turn"
    assert params["p_thread_id"] == str(thread_id)
    assert params["p_user_message_id"] == str(user_message_id)
    assert params["p_assistant_message_id"] == str(assistant_message_id)
    assert params["p_assistant_usage"]["input_tokens"] == 10
    assert params["p_citations"][0]["position"] == 1
