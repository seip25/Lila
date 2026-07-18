# Asynchronous Database & Cache System in Lila Framework

Lila Framework supports fully asynchronous database connections, session management, and cache operations. This allows the application to run without blocking the event loop under heavy concurrent loads.

## Installation of Async Drivers

To use the asynchronous capabilities, you must install the corresponding async database driver:

- SQLite: Included by default (uses aiosqlite).
- MySQL: Requires `aiomysql` (pip install aiomysql).
- PostgreSQL: Requires `asyncpg` (pip install asyncpg).

Ensure these dependencies are added to your project requirements.

## Database Configuration

To enable asynchronous database access, configure the connection dictionary with `is_async: True`.

```python
from lila.core.database import Database

config = {
    "type": "sqlite",
    "database": "lila",
    "is_async": True
}
connection = Database(config=config)
connection.connect()
```

## Session and Transaction Context Manager

For write operations, use the transaction context manager to handle commits and rollbacks automatically.

```python
async with connection.transaction() as db:
    new_user = User(email="user@example.com", name="Lila")
    db.add(new_user)
```

If you need a manual session reference, obtain it through `get_session()` and manage commits or rollback based on `is_async`.

```python
db = connection.get_session()
try:
    user = await User.get_by_email_async(email)
    if connection.is_async:
        await db.commit()
    else:
        db.commit()
finally:
    if connection.is_async:
        await db.close()
    else:
        db.close()
```

## Asynchronous ORM Queries

Lila's `BaseModel` provides non-blocking async variants for model queries with built-in query deduplication.

### Select Operations (Deduplicated)

```python
# Retrieves all records matching filters
items = await Product.get_all_async(limit=100)

# Retrieves a single record by ID
product = await Product.get_by_id_async(product_id)
```

### Write Operations

```python
# Inserts a record asynchronously
await Product.insert_async(db_session, {"name": "Laptop", "price": 999.99})

# Updates a record asynchronously
await Product.update_async(db_session, product_id, {"price": 899.99})

# Deletes a record asynchronously
await Product.delete_async(db_session, product_id)
```

### Non-ORM Query Operations

```python
# Fetch all records without ORM mapping
items = await Product.get_all_without_orm_async(limit=10)

# Fetch a record by ID without ORM mapping
item = await Product.get_by_id_without_orm_async(product_id)
```

### Related Models

```python
# Fetch a single related model instance
category = await product.get_related_async(Category)

# Fetch multiple related model instances
tags = await product.get_related_many_async(Tag)
```

## Custom Raw SQL Queries

You can execute custom raw queries using the database connection manager.

```python
sql = "SELECT id, name FROM products WHERE price > :price LIMIT 10"
products = await connection.query_async(
    sql,
    params={"price": 100.00},
    return_rows=True
)
```

For custom ORM query operations:

```python
instance = Product(name="Smart Watch", price=199.99)
product_id = await connection.query_orm_async(
    model=Product,
    operation="insert",
    instance=instance
)
```

## Redis Asynchronous Cache & Route Caching

Lila supports asynchronous cache operations using the `Cache` class.

```python
from lila.core.cache import Cache

# Set a cache value
await Cache.set_async("my_key", "my_value", ttl=300)

# Get a cache value
value = await Cache.get_async("my_key")

# Delete a cache value
await Cache.delete_async("my_key")

# Clear the database cache
await Cache.clear_async()
```

To cache route responses asynchronously:

```python
from lila.core.cache import cached

@router.get("/products")
@cached(ttl=60)
async def list_products(request: Request):
    items = await Product.get_all_async(limit=50)
    return JSONResponse(items)
```

## Asynchronous Session Management

The `Session` class handles signed cookie sessions with optional Redis backend storage asynchronously.

```python
from lila.core.session import Session

# Get session data
auth_data = await Session.get(request, key="auth")

# Set session data
await Session.set(request, response, data={"user_id": 1}, key="auth")

# Delete session data
await Session.delete(response, key="auth", request=request)
```
