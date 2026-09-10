import clickhouse_connect
import os

# Internal low-latency auth/dashboard path, not a long-running analytical
# query — fail fast so a ClickHouse hiccup can't hang a request for the
# driver's ~10s default and cascade into piled-up browser connections.
CONNECT_TIMEOUT_SECONDS = 3
SEND_RECEIVE_TIMEOUT_SECONDS = 5

def get_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST"),
        port=int(os.getenv("CLICKHOUSE_PORT", 8443)),
        username=os.getenv("CLICKHOUSE_USER"),
        password=os.getenv("CLICKHOUSE_PASSWORD"),
        database=os.getenv("CLICKHOUSE_DATABASE"),
        secure=True,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        send_receive_timeout=SEND_RECEIVE_TIMEOUT_SECONDS
    )
