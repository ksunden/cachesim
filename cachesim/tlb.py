import random
class TLB:
    """TLB which only implements offset translation for now.

    add and some of the bits required for "real" TLB translation are preserved here, but currently only functions as an offset calculator.
    """
    
    def __init__(self, nEntries, bits):
        self.nEntries = nEntries
        self.virtual = [0] * nEntries
        self.physical = [0] * nEntries
        self.freeList = list(range(nEntries))
        self.lastUsed = [0] * nEntries
        self.counter = 0
        self.bits = bits
        self.offset = random.randint(0, (1<<bits)-1)

    def add(self, virtual, physical):
        if len(self.freeList) == 0:
            self.evict()
        i = self.freeList.pop()
        counter += 1
        self.lastUsed[i] = counter
        self.virtual[i] = virtual
        self.physical[i] = physical

    def translateVirt(self, virtualAddress):
        return (virtualAddress - self.offset) % (1<<self.bits)
        i = self.virtual.index(virtualAddress)
        counter += 1
        self.lastUsed[i] = counter
        return self.physical[i]

    def translatePhys(self, physicalAddress):
        return (physicalAddress + self.offset) % (1<<self.bits)
        i = self.physical.index(physicalAddress)
        counter += 1
        self.lastUsed[i] = counter
        return self.virtual[i]
