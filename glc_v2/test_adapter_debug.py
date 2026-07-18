import asyncio
from glc.channels.catalogue.whatsapp.adapter import Adapter
from glc.channels.envelope import ChannelReply

class DummyMock:
    def __init__(self):
        self.send_log = []
    async def send(self, payload):
        self.send_log.append(payload)
        return {"messaging_product": "whatsapp"}

async def main():
    mock = DummyMock()
    adapter = Adapter(config={"mock": mock})
    reply = ChannelReply(channel="whatsapp", channel_user_id="123", text="hi")
    res = await adapter.send(reply)
    print("RES TYPE:", type(res))
    print("RES VAL:", res)

asyncio.run(main())
