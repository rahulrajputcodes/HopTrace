import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "HopTracePass123")

driver = None

def seed_neo4j():
    global driver
    try:
        with driver.session() as session:
            session.run("""
            MERGE (gw1:Device {id: 'GW1', name: 'Upstream Gateway', type: 'Fiber PoP', voltage: '52.8V', status: 'Healthy'})
            MERGE (r1:Device {id: 'R1', name: 'Village Core Router', type: 'Core Tower', voltage: '51.4V', status: 'Healthy'})
            MERGE (wb1:Device {id: 'WB1', name: 'Wireless Bridge Tx', type: 'Hilltop Bridge Tx', voltage: '12.8V', status: 'Healthy'})
            MERGE (wb2:Device {id: 'WB2', name: 'Wireless Bridge Rx', type: 'Village Bridge Rx', voltage: '12.5V', status: 'Healthy'})
            MERGE (ap1:Device {id: 'AP1', name: 'North Village AP', type: 'North Ward AP', voltage: '24V', status: 'Healthy'})
            MERGE (ap2:Device {id: 'AP2', name: 'South Village AP', type: 'South Ward AP', voltage: '24V', status: 'Healthy'})

            MERGE (gw1)-[:CONNECTS_TO {latency: '15ms', loss: '0%'}]->(r1)
            MERGE (r1)-[:CONNECTS_TO {latency: '2ms', loss: '0%'}]->(wb1)
            MERGE (wb1)-[:CONNECTS_TO {latency: '25ms', loss: '0.5%'}]->(wb2)
            MERGE (wb2)-[:CONNECTS_TO {latency: '3ms', loss: '0%'}]->(ap1)
            MERGE (r1)-[:CONNECTS_TO {latency: '5ms', loss: '0%'}]->(ap2)
            """)
    except Exception as e:
        print(f"Neo4j seeding skipped or failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global driver
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("Connected to Neo4j successfully.")
        seed_neo4j()
    except Exception as e:
        print(f"Warning: Could not connect to Neo4j: {e}")
    yield
    if driver:
        driver.close()

app = FastAPI(title="HopTrace Network Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/api/health")
@app.get("/health")
def health_check():
    neo4j_alive = False
    if driver:
        try:
            driver.verify_connectivity()
            neo4j_alive = True
        except Exception:
            neo4j_alive = False
    return {"status": "ok", "service": "HopTrace API", "neo4j": "connected" if neo4j_alive else "disconnected"}

@app.get("/api/topology")
def get_topology():
    if not driver:
        return {"nodes": [], "links": []}
    with driver.session() as session:
        result = session.run("MATCH (n:Device) RETURN n.id AS id, n.name AS name, n.type AS type, n.voltage AS voltage, n.status AS status")
        nodes = [record.data() for record in result]
        result_links = session.run("MATCH (a:Device)-[r:CONNECTS_TO]->(b:Device) RETURN a.id AS source, b.id AS target, r.latency AS latency, r.loss AS loss")
        links = [record.data() for record in result_links]
    return {"nodes": nodes, "links": links}
