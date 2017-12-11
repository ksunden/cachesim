#! /usr/bin/env python
import math
import sys
from cache import Cache

class Hub:
    

    def __init__(self, nLines=0x1000, associativity=8, pageSize=0x1000, cache=None):
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
        self.pageSize = pageSize
        self.cache = cache
        self.eTLB = None #set in ETLB, circular refererence

        if self.associativity == -1:
            self.associativity = self.nLines

        if self.cache is None:
            self.cache = Cache(size=0x100000, associativity=16)
            self.cache.accessTime = 7
            self.cache.tagTime = 3
            self.cache.accessEnergy = 0.136191
            self.cache.tagEnergy = 0.00221937

        self.cacheLine = self.cache.cacheLine

        self.nSets = self.nLines // self.associativity

        self.offsetBits = int(math.ceil(math.log2(self.cacheLine)))
        self.pageBits = int(math.ceil(math.log2(self.pageSize))) - self.offsetBits
        self.setBits = int(math.ceil(math.log2(self.nSets)))
        self.tagBits = 48 - self.setBits - self.pageBits - self.offsetBits

        self.freeList = [list(range(self.associativity)) for i in range(self.nSets)]

        self.counter = 0
        self.entries = [[HubEntry(self.pageSize, self.cacheLine) for i in range(self.associativity)] for j in range(self.nSets)]

        self.hit = [0,0,0,0] #DRAM,L1I,L1D,L2  Note: L1 is actually a unified cache at present, for forward compatability if separate caches are ever implemented
        self.miss = 0
        
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
        offset = address % self.cacheLine
        pageIndex = (address >> self.offsetBits) % (1 << self.pageBits)
        setIndex = (address >> (self.offsetBits + self.pageBits))  % self.nSets

        tag = address >> (self.setBits + self.pageBits + self.offsetBits)

        if countTime is None:
            countTime = count

        if countEnergy is None:
            countEnergy = count

        # Hub Hit
        hit = False
        for i,entry in enumerate(self.entries[setIndex]):
            if entry.ptag == tag:
                hit = True
                loc = entry.location[pageIndex]
                way = entry.way[pageIndex]
                if count:
                    self.hit[loc] += 1
                return entry

        # Hub Miss fig3e
        if not hit:
            if count:
                self.miss += 1

            # select a victim step 1
            if len(self.freeList[setIndex]) == 0:
                way = self.evict(setIndex)
                hubEntry = self.entrys[setIndex][way]
                L1Set = hubEntry.eTLBPointer % self.eTLB.cache.nSets
                L2Set = hubEntry.ptag % self.cache.nSets

                # Walk CLT, and evict (step 2)
                for i,loc,w in zip(range(hubEntry.nEntries), hubentry.location, hubentry.way):
                    if loc == 0: # not in cache
                        pass
                    elif loc == 1 or loc == 2: # In L1, combined instr/data, split if caches split
                        self.eTLB.evictCache(L1Set, w, countEnergy=countEnergy)
                    elif loc == 3: # In L2
                        self.evictCache(L2Set, w, countEnergy=countEnergy)
                
                etlbSet = hubEntry.eTLBPointer % self.eTLB.nSets
                etlbWay = hubEntry.eTLBPointer >> self.eTLB.setBits

                # invalidate the eTLB CLT (step 3)
                self.eTLB.entries[etlbSet][etlbWay].valid = False
                
            # Install the new page (step 4)
            way = self.freeList[setIndex].pop()
            entry = self.entries[setIndex][way]
            entry.ptag = tag
            entry.eTLBValid = False
            entry.location = [0] * entry.nEntries
            entry.valid = True
            
        
        self.counter += 1
        self.entries[setIndex][way].lastAccess = self.counter
        return self.entries[setIndex][way]

    def evict(self, setNumber, way=None):
        """Evict (i.e. add to the free list) a cache line.
        
        If `way` is None, LRU replacement policy is used among occupied lines.
        If `way` is an integer, that integer is added to the free list.
        """
        if way is not None:
            self.freeList[setNumber].append(way)
            return way
        else:
            index = 0
            minAccess = self.entries[setNumber][0].lastAccess
            for i,acc in enumerate(self.entries[setNumber]):
                if i not in self.freeList[setNumber] and self.entries[setNumber][i].lastAccess < minAccess:# and self.entries[setNumber][i].etlbValid == False:
                    index = i
                    minAccess = self.entries[setNumber][i].lastAccess
            if index not in self.freeList[setNumber]:
                self.freeList[setNumber].append(index)
            self.entries[setNumber][index].eTLBValid = False
            return index

    def evictCache(self, setNumber, way=None, countEnergy=True):
        # Fig3f
        # Select A Victim, acess its hub pointer (step 1)
        if way == None:
            way = self.cache.selectEviction(setNumber)
        hubPointer = self.cache.tags[setNumber][way]

        # Move the data/hub pointer (step 4)
        # Access to DRAM not simultated
        self.cache.accessDirect(setNumber, way, write=False, countEnergy=countEnergy)

        # Update the active CLT (step 5)
        hubSet = hubPointer % self.nSets
        hubWay = hubPointer >> self.setBits

        hubEntry = self.entries[hubSet][hubWay]

        if hubEntry.eTLBValid:
            etlbSet = hubEntry.eTLBPointer % self.nSets
            etlbWay = hubEntry.eTLBPointer >> self.setBits

            entry = self.entries[etlbSet][etlbWay]
            for pageIndex in range(entry.nEntries):
                if entry.location[pageIndex] == 2 and entry.location[pageIndex] == way:
                    entry.location[pageIndex] = 0 #NIC
        else:
            for pageIndex in range(hubEntry.nEntries):
                if hubEntry.location[pageIndex] == 2 and hubEntry.location[pageIndex] == way:
                    hubEntry.location[pageIndex] = 0 #NIC
        # Actually evict
        self.cache.evict(setNumber, way, countEnergy=countEnergy)


class HubEntry:
    

    def __init__(self, pageSize=0x1000, cacheLine=64):
        self.ptag = 0
        self.eTLBValid = False
        self.instrOrData = True # Data, unused at present
        self.eTLBPointer = 0

        self.lastAccess = 0

        self.pageSize = pageSize
        self.cacheLine = cacheLine

        self.nEntries = self.pageSize // self.cacheLine

        self.valid = False
        self.location = [0] * self.nEntries
        self.way = [0] * self.nEntries

