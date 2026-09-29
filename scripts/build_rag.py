import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rag import build_vectorstore


if __name__ == "__main__":
    build_vectorstore()