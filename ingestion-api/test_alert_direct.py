from dotenv import load_dotenv
load_dotenv()

from clickhouse_client import get_client
from alerts import check_graduated_alert

client = get_client()

result = check_graduated_alert(
    client=client,
    trace_id="d1118240-9668-44f9-8caf-be2a6c559dab",
    customer_id="cust-001",
    current_value=261,
    limit=300
)

print(result)