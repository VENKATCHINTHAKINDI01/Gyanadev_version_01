from dotenv import load_dotenv
load_dotenv()
from db.qdrant_store import QdrantStore
import os
s = QdrantStore(os.getenv('QDRANT_URL'), os.getenv('QDRANT_API_KEY'))
s.client.delete_collection('book_chunks')
print('Collection deleted')