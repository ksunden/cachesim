#! /usr/bin/env python
import math
import sys
from hub import Hub
from cache import Cache
from tlb import TLB

class ETLB:
    

    def __init__(self, nLines=64, associativity=8, pageSize=0x1000, tlb=None, cache=None, hub=None):
        """Simple associative cache.

        Parameters
        ----------

        size (int):
            Cache size in bytes. (Default 0x8000 (32 kB))
        associtivilty (int):
            Number of ways for an associative cache, -1 for fully associative.
        cacheLine (int):
            Number of bytes per cache line, determiines the number of offset bits.
        child (Cache):
            The next level of cache, must be a hub for etlb, default is None, which means default Hub.
        """
        self.nLines = nLines
        self.associativity = associativity
        self.hub = hub
        self.cache = cache
        self.tlb = tlb
        self.pageSize = pageSize


        if self.associativity == -1:
            self.associativity = self.nLines

        if self.hub is None:
            self.hub = Hub(associativity=self.associativity, pageSize=self.pageSize)
        if self.cache is None:
            self.cache = Cache(size=0x8000, associativity=16)
            self.cache.accessEnergy = 0.0111033
            self.cache.accessTime = 4
            self.cache.tagTime = 1
            self.cache.tagEnergy = 0.000539962

        self.hub.eTLB = self

        self.cacheLine = self.cache.cacheLine

        self.nSets = self.nLines // self.associativity

        self.offsetBits = int(math.ceil(math.log2(self.cacheLine)))
        self.wayBits = int(math.ceil(math.log2(self.associativity)))
        self.pageBits = int(math.ceil(math.log2(self.pageSize))) - self.offsetBits
        self.setBits = int(math.ceil(math.log2(self.nSets)))
        self.tagBits = 48 - self.setBits - self.pageBits - self.offsetBits

        if self.tlb is None:
            self.tlb = TLB(512, self.tagBits + self.setBits)

        self.freeList = [list(range(self.associativity)) for i in range(self.nSets)]

        self.counter = 0
        self.entries = [[ETLBEntry(self.pageSize, self.cacheLine) for i in range(self.associativity)] for j in range(self.nSets)]

        self.hit = [0,0,0,0] #DRAM,L1I,L1D,L2  Note: L1 is actually a unified cache at present, for forward compatability if separate caches are ever implemented
        self.miss = 0
        self.cycles = 0
        self.energy = 0.

        
    def access(self, address, write=False, count=True, countTime=None, countEnergy=None):
        """Access a given address.

        Parameters
        ----------
        address (int):
            The address which is accessed.
        write (bool):
            True if the access is a write, False for a read (default read).
            This parameter is unused currently, but maintained for future use.
        count (bool):
            Whether hit/miss rate should be counted (default is True).
        """
        # Step 1 in fig2/3d
        offset = address % self.cacheLine
        pageIndex = (address >> self.offsetBits) % (1 << self.pageBits)
        setIndex = (address >> (self.offsetBits + self.pageBits))  % self.nSets

        tag = address >> (self.setBits + self.pageBits + self.offsetBits)

        if countTime is None:
            countTime = count

        if countEnergy is None:
            countEnergy = count

        #eTLB Hit
        hit = False
        for i,entry in enumerate(self.entries[setIndex]):
            if entry.valid and entry.vtag == tag:
                hit = True
                loc = entry.location[pageIndex]
                way = entry.way[pageIndex]
                if count:
                    self.hit[loc] += 1
                # Not in cache fig2c
                if loc == 0:
                    # Access to DRAM not simulated, send to CPU (step 2/3)
                    # ((entry.paddr << self.pageBits) + pageIndex ) <<self.offsetBits) + offset
                    # Evict from L1 (step 4)
                    L1Set = (address >> (self.offsetBits + self.pageBits))  % self.cache.nSets
                    if len(self.cache.freeList[L1Set]) == 0:
                        self.evictCache(L1Set, countEnergy=countEnergy)
                    # Update Hub pointer, place data (step 5)
                    L1Way = self.cache.freeList[L1Set].pop()
                    self.cache.accessDirect(L1Set, L1Way, countTime=False, countEnergy=countEnergy)
                    etlbPointer = (i << self.setBits) + setIndex
                    hubWay = 0
                    hubSet = entry.paddr % self.hub.nSets
                    for j in range(self.hub.associativity):
                        if self.hub.entries[hubSet][j].valid and self.hub.entries[hubSet][j].eTLBPointer == etlbPointer:
                            hubWay = j
                            break
                    self.cache.tags[L1Set][L1Way] = (hubWay << self.hub.setBits) + (entry.paddr % self.hub.nSets)
    
                    # Update the CLT (step 6)
                    entry.location[pageIndex] = 2 #L1D (unified L1)
                    entry.way[pageIndex] = L1Way
                # In L1 (data and instruction caches unified, this needs to be split if those are split) fig2a
                elif loc == 1 or loc == 2:
                    # access the L1 cache entry, send to CPU (step 2/3)
                    cacheSetIndex = (address >> self.offsetBits) % self.cache.nSets
                    self.cache.accessDirect(cacheSetIndex, way, countTime=countTime, countEnergy=countEnergy)
                # In L2 fig2b
                elif loc == 3:
                    # access the L2 cache entry, send to CPU (step 2/3)
                    cacheSetIndex = entry.paddr % self.hub.cache.nSets
                    self.hub.cache.accessDirect(cacheSetIndex, way, countTime=countTime, countEnergy=countEnergy)
                    # Evict from L1 (step 4)
                    L1Set = (address >> (self.offsetBits + self.pageBits))  % self.cache.nSets
                    if len(self.cache.freeList[L1Set]) == 0:
                        self.evictCache(L1Set, countEnergy=countEnergy)
                    # Update Hub pointer, place data (step 5)
                    L1Way = self.cache.freeList[L1Set].pop()
                    self.cache.accessDirect(L1Set, L1Way, countTime=False, countEnergy=countEnergy)
                    self.cache.tags[L1Set][L1Way] = self.hub.cache.tags[cacheSetIndex][way]
    
                    # Update the CLT (step 6)
                    entry.location[pageIndex] = 2 #L1D (unified L1)
                    entry.way[pageIndex] = L1Way

                    # Free the L2 entry so it can be used again (Only one copy, which is now in L1)
                    self.hub.cache.evict(cacheSetIndex, way, countEnergy=countEnergy)
                # Invalid location
                else:
                    raise ValueError("Location in CLT is invalid, expected 2 bit int, got %d"%loc)
                way = i
                break
        
        #eTLB Miss fig3d
        if not hit:
            if count:
                self.miss += 1
            # Evict if necessary (step 2)
            if len(self.freeList[setIndex]) == 0:
                self.evict(setIndex)
            way = self.freeList[setIndex].pop()
            entry = self.entries[setIndex][way]

            # Update the virtual and physical address, calling the TLB (step 3)
            entry.vtag = tag
            entry.paddr = self.tlb.translateVirt((tag << self.setBits) + setIndex)
            addr = (((entry.paddr << self.pageBits) + pageIndex) << self.offsetBits) + offset
            # access the Hub (step 4)
            hubEntry = self.hub.access(addr, write=write, count=count, countEnergy=countEnergy, countTime=countTime)

            # Copy the CLT (step 5)
            entry.way = hubEntry.way.copy()
            entry.location = hubEntry.location.copy()
            entry.valid = True

            hubSet = entry.paddr % self.hub.nSets

            # Update the eTLBPointer, and Valid bit (step 6)
            hubEntry.eTLBValid = True
            hubEntry.eTLBPointer = (way << self.setBits) + setIndex
            self.access(address, write, count=False, countEnergy=True, countTime=False)
        
        self.counter += 1
        self.entries[setIndex][way].lastAccess = self.counter

    def evict(self, setNumber, way=None):
        """Evict (i.e. add to the free list) a cache line.
        
        If `way` is None, LRU replacement policy is used among occupied lines.
        If `way` is an integer, that integer is added to the free list.
        """
        if way is not None:
            if way not in self.freeList[setNumber]:
                self.freeList[setNumber].append(way)
            return way
        else:
            way = 0
            minAccess = self.entries[setNumber][0].lastAccess
            entry = self.entries[setNumber][0]
            for i,ent in enumerate(self.entries[setNumber]):
                if i not in self.freeList[setNumber] and self.entries[setNumber][i].lastAccess < minAccess:
                    way = i
                    minAccess = self.entries[setNumber][i].lastAccess
                    entry = self.entries[setNumber][i]

            eTLBPointer = (way << self.setBits) + setNumber
            hubSet = entry.paddr % self.hub.nSets
            hubWay = -1
            for i in range(self.hub.associativity):
                if self.hub.entries[hubSet][i].eTLBPointer == eTLBPointer:
                    hubWay = i
                    break
            if hubWay == -1:
                raise RuntimeError("Entry not in hub when expected")
            self.hub.entries[hubSet][hubWay].location = entry.location.copy()
            self.hub.entries[hubSet][hubWay].way = entry.way.copy()
            self.hub.entries[hubSet][hubWay].eTLBValid = False

            if way not in self.freeList[setNumber]:
                self.freeList[setNumber].append(way)
            return way

    def evictCache(self, setNumber, way=None, countEnergy=True):
        # Fig3f
        # Select A Victim, acess its hub pointer (step 1)
        if way == None:
            way = self.cache.selectEviction(setNumber)
        hubPointer = self.cache.tags[setNumber][way]

        # Find the set (step 2)
        L2Set = hubPointer % self.hub.cache.nSets

        # If needed, evict a line (step 3)
        if len(self.hub.cache.freeList[L2Set]) == 0:
            self.hub.evictCache(L2Set, countEnergy=countEnergy)
        # Move the data/hub pointer (step 4)
        L2Way = self.hub.cache.freeList[L2Set].pop()
        self.hub.cache.accessDirect(L2Set, L2Way, countTime=False, countEnergy=countEnergy)
        self.hub.cache.tags[L2Set][L2Way] = hubPointer

        # Update the active CLT (step 5)
        hubSet = hubPointer % self.hub.nSets
        hubWay = hubPointer >> self.hub.setBits

        hubEntry = self.hub.entries[hubSet][hubWay]

        if hubEntry.eTLBValid:
            etlbSet = hubEntry.eTLBPointer % self.nSets
            etlbWay = hubEntry.eTLBPointer >> self.setBits
            
            entry = self.entries[etlbSet][etlbWay]
            for pageIndex in range(entry.nEntries):
                if entry.location[pageIndex] == 2 and entry.location[pageIndex] == way:
                    entry.location[pageIndex] = 3 #L2
                    entry.way[pageIndex] = L2Way
        else:
            for pageIndex in range(hubEntry.nEntries):
                if hubEntry.location[pageIndex] == 2 and hubEntry.location[pageIndex] == way:
                    hubEntry.location[pageIndex] = 3 #L2
                    hubEntry.way[pageIndex] = L2Way
        # Actually evict
        self.cache.evict(setNumber, way, countEnergy=countEnergy)    

class ETLBEntry:
    

    def __init__(self, pageSize=0x1000, cacheLine=64):
        self.vtag = 0
        self.paddr = 0

        self.lastAccess = 0

        self.pageSize = pageSize
        self.cacheLine = cacheLine

        self.nEntries = self.pageSize // self.cacheLine

        self.valid = False
        self.location = [0] * self.nEntries
        self.way = [0] * self.nEntries

    

def test():
    etlb = ETLB()
    nLines = -1
    if len(sys.argv) > 1:
        nLines = int(sys.argv[1])
    skip = 0
    if len(sys.argv) > 2:
        skip = int(sys.argv[2])
    warmup = 0
    if len(sys.argv) > 3:
        warmup = int(sys.argv[3])
    counter = 0
    for i, line in enumerate(sys.stdin):
        if line.startswith('#eof'):
            break
        if i >= skip:
            if i >= skip+warmup:
                counter += 1
            addr = int(line.split(' ')[1], 16)
            #print(line, i)
            etlb.access(addr, line[0]=='W', i >= skip + warmup)
        if i + 1 == skip + warmup + nLines and nLines != -1:
            break
    print("N:", counter)
    print("ETLB Hit, NIC %d, (%03f)"%(etlb.hit[0], etlb.hit[0]/(counter)*100))
    print("ETLB Hit, L1D %d, (%03f)"%(etlb.hit[2], etlb.hit[2]/(counter)*100))
    print("ETLB Hit, L2  %d, (%03f)"%(etlb.hit[3], etlb.hit[3]/(counter)*100))
    print("ETLB Miss,    %d, (%03f)"%(etlb.miss, etlb.miss/(counter)*100))
    print("Hub Hit, NIC %d, (%03f)"%(etlb.hub.hit[0], etlb.hub.hit[0]/(counter)*100))
    print("Hub Hit, L1  %d, (%03f)"%(etlb.hub.hit[2], etlb.hub.hit[2]/(counter)*100))
    print("Hub Hit, L2  %d, (%03f)"%(etlb.hub.hit[3], etlb.hub.hit[3]/(counter)*100))
    print("Hub Miss,    %d, (%03f)"%(etlb.hub.miss, etlb.hub.miss/(counter)*100))

    print("Time L1: %d, L2: %d, total: %d"%(etlb.cache.cycles, etlb.hub.cache.cycles, etlb.cache.cycles+etlb.hub.cache.cycles))
    print("Energy L1: %0.3f, L2: %0.3f, total: %0.3f"%(etlb.cache.energy, etlb.hub.cache.energy, etlb.cache.energy+etlb.hub.cache.energy))


if __name__ == '__main__':
    test()
