import hashlib
import json
import time


class Block:
    def __init__(self, index, data, previous_hash):
        self.index = index
        self.timestamp = time.time()
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }

        block_string = json.dumps(block_data, sort_keys=True)

        return hashlib.sha256(block_string.encode()).hexdigest()
    
class Blockchain:

    def __init__(self):

        self.chain = []

        self.create_genesis_block()

    def create_genesis_block(self):

        genesis = Block(
            0,
            {
                "user": "GENESIS",
                "action": "genesis"
            },
            "0"
        )

        self.chain.append(genesis)

    def add_block(self, data):

        previous_block = self.chain[-1]

        new_block = Block(
            len(self.chain),
            data,
            previous_block.hash
        )

        self.chain.append(new_block)

    def is_valid(self):

        for i in range(1, len(self.chain)):

            current = self.chain[i]
            previous = self.chain[i - 1]

            # Verify chain linkage
            if current.previous_hash != previous.hash:
                return False

            # Verify current block hash
            if current.calculate_hash() != current.hash:
                return False

        return True
