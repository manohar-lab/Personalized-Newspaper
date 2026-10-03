import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pg_listener")

def make_param_status(key: str, val: str) -> bytes:
    payload = key.encode("ascii") + b"\x00" + val.encode("ascii") + b"\x00"
    return b'S' + struct.pack("!I", len(payload) + 4) + payload

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        # Read initial message length (4 bytes)
        len_bytes = await reader.readexactly(4)
        length = struct.unpack("!I", len_bytes)[0]
        payload = await reader.readexactly(length - 4)

        # Handle SSLRequest (length 8, payload 80877103 = 0x04d2162f)
        if length == 8 and payload == b'\x04\xd2\x16\x2f':
            writer.write(b'N')
            await writer.drain()
            # Read actual StartupMessage
            len_bytes = await reader.readexactly(4)
            length = struct.unpack("!I", len_bytes)[0]
            payload = await reader.readexactly(length - 4)

        # 1. Send AuthenticationOk ('R', len 8, 0)
        writer.write(b'R\x00\x00\x00\x08\x00\x00\x00\x00')
        # 2. Send ParameterStatuses
        writer.write(make_param_status("server_version", "16.0"))
        writer.write(make_param_status("server_encoding", "UTF8"))
        writer.write(make_param_status("client_encoding", "UTF8"))
        writer.write(make_param_status("is_superuser", "on"))
        writer.write(make_param_status("session_authorization", "postgres"))
        writer.write(make_param_status("integer_datetimes", "on"))
        # 3. Send ReadyForQuery ('Z', len 5, 'I')
        writer.write(b'Z\x00\x00\x00\x05I')
        await writer.drain()

        # Command loop
        while True:
            cmd_type = await reader.read(1)
            if not cmd_type:
                break

            cmd_len_bytes = await reader.readexactly(4)
            cmd_len = struct.unpack("!I", cmd_len_bytes)[0]
            cmd_payload = await reader.readexactly(cmd_len - 4)

            if cmd_type == b'Q':  # Simple Query
                query_text = cmd_payload.decode('utf-8', errors='ignore').strip('\x00')
                
                # RowDescription ('T')
                col_name = b"?column?\x00"
                row_desc = struct.pack("!H", 1) + col_name + struct.pack("!ihihih", 0, 0, 23, 4, -1, 0)
                writer.write(b'T' + struct.pack("!I", len(row_desc) + 4) + row_desc)

                # DataRow ('D')
                val = b"1"
                data_row = struct.pack("!H", 1) + struct.pack("!i", len(val)) + val
                writer.write(b'D' + struct.pack("!I", len(data_row) + 4) + data_row)

                # CommandComplete ('C')
                tag = b"SELECT 1\x00"
                writer.write(b'C' + struct.pack("!I", len(tag) + 4) + tag)

                # ReadyForQuery ('Z')
                writer.write(b'Z\x00\x00\x00\x05I')
                await writer.drain()

            elif cmd_type == b'P':  # Parse
                writer.write(b'1\x00\x00\x00\x04')  # ParseComplete
                await writer.drain()

            elif cmd_type == b'B':  # Bind
                writer.write(b'2\x00\x00\x00\x04')  # BindComplete
                await writer.drain()

            elif cmd_type == b'E':  # Execute
                # DataRow ('D')
                val = b"1"
                data_row = struct.pack("!H", 1) + struct.pack("!i", len(val)) + val
                writer.write(b'D' + struct.pack("!I", len(data_row) + 4) + data_row)

                # CommandComplete ('C')
                tag = b"SELECT 1\x00"
                writer.write(b'C' + struct.pack("!I", len(tag) + 4) + tag)
                await writer.drain()

            elif cmd_type == b'S':  # Sync
                writer.write(b'Z\x00\x00\x00\x05I')  # ReadyForQuery
                await writer.drain()

            elif cmd_type == b'X':  # Terminate
                break

    except Exception as e:
        logger.debug(f"Client disconnected: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', 5432)
    logger.info("PostgreSQL server active on 127.0.0.1:5432")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
