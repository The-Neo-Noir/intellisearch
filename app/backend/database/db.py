from mongoengine import connect

print('#####')
connect(
    db="bonds_db",
    host="localhost",
    port=27017,
    alias="default"  # 🔥 THIS IS CRITICAL
)


def init_db():
    connect(db="bonds_db", host="localhost", port=27017, alias="default")
