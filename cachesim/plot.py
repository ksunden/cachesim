#! /usr/bin/env python3

from matplotlib import pyplot as plt
from matplotlib.gridspec import GridSpec
import sys
import numpy as np


N = []
L1 = []
L2 = []
Mem = []

ETLB = []
Hub = []

time = []
energy = []

for line in sys.stdin:
    spl = line.split(' ')
    if spl[0] == 'N:':
        N.append(int(spl[1]))
    elif spl[0] == 'L1':
        if spl[1] == 'hit:':
            L1.append(int(spl[-2]))
    elif spl[0] == 'L2':
        if spl[1] == 'hit:':
            L2.append(int(spl[-2]))
        elif spl[1] == 'miss:':
            Mem.append(int(spl[-2]))
    elif spl[0] == 'ETLB':
        if spl[2] == 'NIC':
            ETLB.append([0,0,int(spl[-2][:-1])])
        elif spl[2] == 'L1D':
            ETLB[-1][0] = int(spl[-2][:-1])
        elif spl[2] == 'L2':
            ETLB[-1][1] = int(spl[-2][:-1])
    elif spl[0] == 'Hub':
        if spl[2] == 'NIC':
            Hub.append([0,0,int(spl[-2][:-1]), 0])
        elif spl[2] == 'L1':
            Hub[-1][0] = int(spl[-2][:-1])
        elif spl[2] == 'L2':
            Hub[-1][1] = int(spl[-2][:-1])
        else:
            Hub[-1][-1] = int(spl[-2][:-1])

    elif spl[0] == 'Time':
        time.append([int(spl[2][:-1]), int(spl[4][:-1])])
    elif spl[0] == 'Energy':
        energy.append([float(spl[2][:-1]), float(spl[4][:-1])])


labels = sys.argv[1:]

# Data Accesses
bar_width = 0.2
index = np.arange(len(N)//2)
gs = GridSpec(3,1)

ax = plt.subplot(gs[0,0])
ax.bar(index, np.asarray(L1)/(np.asarray([N[i] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C0', label='Base')
ax.bar(index + 2*bar_width, (np.asarray(ETLB)[:,0] + np.asarray(Hub)[:,0])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C4', label='Total Accesses')
ax.bar(index + 3*bar_width, (np.asarray(ETLB)[:,0])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C7', label='Direct Accesses')
ax.set_ylabel("L1")
ax.set_xticks((),())

ax = plt.subplot(gs[1,0])
ax.bar(index, np.asarray(L2)/(np.asarray([N[i] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C0', label='Base')
ax.bar(index + 2*bar_width, (np.asarray(ETLB)[:,1] + np.asarray(Hub)[:,1])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C4', label='Total Accesses')
ax.bar(index + 3*bar_width, (np.asarray(ETLB)[:,1])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C7', label='Direct Accesses')
ax.set_ylabel("L2")

ax.set_xticks((),())
ax = plt.subplot(gs[2,0])
ax.bar(index, np.asarray(Mem)/(np.asarray([N[i] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C0', label='Base')
ax.bar(index + 2*bar_width, (np.asarray(ETLB)[:,2] + np.asarray(Hub)[:,2] + np.asarray(Hub)[:,3])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C4', label='Total Accesses')
ax.bar(index + 3*bar_width, (np.asarray(ETLB)[:,2])/(np.asarray([N[i+1] for i in range(0,len(N),2)])) * 1000,
            width=bar_width, color='C7', label='Direct Accesses')
ax.set_ylabel("Main Memory")
ax.set_xticks((),())
ax.set_xticks(index + bar_width*3/2)
ax.set_xticklabels(labels)

#Time
plt.figure()
for i in range(0,len(time), 2):
    normtime = time[i][0] + time[i][1]
    L1ref = time[i][0]/normtime
    L2ref = time[i][1]/normtime
    L1etlb = time[i+1][0]/normtime
    L2etlb = time[i+1][1]/normtime
    plt.bar(i//2, L1ref, color='C0', width=bar_width)
    plt.bar(i//2, L2ref, color='C1', bottom=L1ref, width=bar_width)
    plt.bar(i//2+bar_width, L1etlb, color='C0', width=bar_width)
    plt.bar(i//2+bar_width, L2etlb, color='C1', bottom=L1etlb, width=bar_width)

ax = plt.gca()
plt.ylabel("Relative speed")
ax.set_xticks((),())
ax.set_xticks(index + bar_width/2)
ax.set_xticklabels(labels)

#Energy
plt.figure()
for i in range(0,len(energy), 2):
    normenergy = energy[i][0] + energy[i][1]
    L1ref = energy[i][0]/normenergy
    L2ref = energy[i][1]/normenergy
    L1etlb = energy[i+1][0]/normenergy
    L2etlb = energy[i+1][1]/normenergy
    plt.bar(i//2, L1ref, color='C3', width=bar_width)
    plt.bar(i//2, L2ref, color='C2', bottom=L1ref, width=bar_width)
    plt.bar(i//2+bar_width, L1etlb, color='C3', width=bar_width)
    plt.bar(i//2+bar_width, L2etlb, color='C2', bottom=L1etlb, width=bar_width)

ax = plt.gca()
ax.set_ylabel("Relative Energy Use")
ax.set_xticks((),())
ax.set_xticks(index + bar_width/2)
ax.set_xticklabels(labels)
plt.show()
