"""Column roles used to interpret an uploaded retail file."""

ROLES: tuple[str, ...] = (
    "invoice_id",
    "invoice_date",
    "stock_code",
    "description",
    "quantity",
    "unit_price",
    "customer_id",
    "country",
    "category",
    "unit_cost",
)

REQUIRED_FOR_SALES: tuple[str, ...] = ("invoice_date", "quantity", "unit_price")
REQUIRED_FOR_CUSTOMERS: tuple[str, ...] = ("customer_id",)

ROLE_LABELS: dict[str, str] = {
    "invoice_id": "Invoice",
    "invoice_date": "Invoice date",
    "stock_code": "Product code",
    "description": "Description",
    "quantity": "Quantity",
    "unit_price": "Unit price",
    "customer_id": "Customer",
    "country": "Country or region",
    "category": "Category",
    "unit_cost": "Unit cost",
}

ALIASES: dict[str, tuple[str, ...]] = {
    "invoice_id": ("invoice", "invoiceno", "invoicenumber", "invoiceid", "orderid", "ordernumber"),
    "invoice_date": ("invoicedate", "invoicedt", "orderdate", "date"),
    "stock_code": ("stockcode", "sku", "productcode", "productid", "itemcode"),
    "description": ("description", "productname", "product", "item"),
    "quantity": ("quantity", "qty"),
    "unit_price": ("unitprice", "price", "unitamount"),
    "customer_id": ("customerid", "customer", "buyerid"),
    "country": ("country", "region"),
    "category": ("category", "productcategory"),
    "unit_cost": ("unitcost", "cost"),
}


def normalize_header(value: object) -> str:
    text = str(value).strip().lower().replace("_", " ")
    return "".join(text.split())


def empty_mapping() -> dict[str, str | None]:
    return {role: None for role in ROLES}


def suggest_mapping(columns: list[str]) -> dict[str, str | None]:
    mapping = empty_mapping()
    used: set[str] = set()
    normalized = {column: normalize_header(column) for column in columns}
    for role in ROLES:
        aliases = {normalize_header(alias) for alias in ALIASES[role]}
        for column, key in normalized.items():
            if column in used or key not in aliases:
                continue
            mapping[role] = column
            used.add(column)
            break
    return mapping


def clean_mapping(raw: dict | None) -> dict[str, str | None]:
    mapping = empty_mapping()
    if not isinstance(raw, dict):
        return mapping
    for role in ROLES:
        value = raw.get(role)
        if isinstance(value, str) and value.strip():
            mapping[role] = value.strip()
    return mapping


def missing_sales_roles(mapping: dict[str, str | None]) -> list[str]:
    return [role for role in REQUIRED_FOR_SALES if not mapping.get(role)]
