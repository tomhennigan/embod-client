from uuid import UUID
from struct import pack_into, unpack_from
import asyncio
import websockets
import logging

class Client:
    """

    """

    ADD_AGENT = bytes([0])
    REMOVE_AGENT = bytes([1])
    AGENT_ACTION = bytes([2])
    AGENT_STATE = bytes([3])

    ERROR = bytes([255])

    def __init__(self, host, apikey, agent_id, state_callback):
        """

        :param apikey:
        :param state_callback:
        """

        self._agent_id = agent_id

        self._state_callback = state_callback

        self._running = False

        self._logger = logging.getLogger("embodclient")

        self._apikey = apikey

        self._endpoint = host+"/v0/agent/control"

    async def _add_agent(self):
        """

        :param agent_id:
        :return:
        """

        await self._send_message_async(Client.ADD_AGENT, self._agent_id)
        self._logger.info("Adding agent %s to environment" % self._agent_id)

    async def _remove_agent(self):
        """

        :param agent_id:
        :return:
        """

        await self._send_message_async(Client.REMOVE_AGENT, self._agent_id)
        self._logger.info("Removing agent %s from environment" % self._agent_id)

    async def send_agent_action(self, action):
        """

        :return:
        """

        await self._send_message_async(Client.AGENT_ACTION, self._agent_id, action)

    async def _start_async(self):

        try:
            self._websocket = await websockets.connect("%s?apikey=%s" % (self._endpoint, self._apikey))
            self._logger.info("Connected to %s" % self._endpoint)
            self._connected = True
        except:
            self._logger.error("Cannot connect to %s" % self._endpoint)
            self._connected = False
            return

        await self._add_agent()

        self._running = True

        try:
            while self._running:
                message = await self._websocket.recv()
                await self._handle_message_async(message)
        except websockets.ConnectionClosed as e:
            self._logger.error("Connection closed, cannot recieve more messages", e)


    def start(self):
        asyncio.get_event_loop().run_until_complete(self._start_async())

    def stop(self):
        self._running = False

    async def _handle_message_async(self, data):
        """

        :return:
        """

        message_type, resource_id_bytes, message_size = unpack_from('>c16si', data, 0)

        resource_id = UUID(bytes=resource_id_bytes)

        state = None
        error = None
        reward = None

        try:
            if message_type == Client.AGENT_STATE:
                reward = unpack_from(">f", data, 21)[0]
                state = unpack_from(">25f", data, 25)
            elif message_type == Client.ERROR:
                error = state = unpack_from("%ds" % message_size, data, 21)
        except:
            self._logger.warn("invalid message received")

        await self._state_callback(state, reward, error)


    async def _send_message_async(self, message_type, resource_id, data=None):
        """

        :param message_type:
        :param resource_id:
        :param data:
        :return:
        """

        if not self._connected:
            self._logger.error("Cannot send message if loop is not running")
            return

        payload_size = len(data)*4 if data is not None else 0
        buffer_size = 21+payload_size

        buffer = bytearray(buffer_size)

        pack_into("c", buffer, 0, message_type)
        pack_into("16s", buffer, 1, resource_id.bytes)

        if data is not None:
            pack_into(">i", buffer, 17, payload_size)
            pack_into(">%df" % (payload_size/4), buffer, 21, *data)
        else:
            pack_into(">i", buffer, 17, 0)

        await self._websocket.send(bytes(buffer))