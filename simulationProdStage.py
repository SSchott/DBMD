from openmm.app.statedatareporter import StateDataReporter
from openmm.app import *
from openmm import *
from openmm.unit import *
from DLGaMDSimulationIntegrator import *
from utils import *
from simParams import *
import pandas as pd, numpy as np, os, sys
"""
OpenMM Application Manual: http://docs.openmm.org/7.2.0/userguide/application.html
"""
for cycle in np.arange(ncycprodstart, ncycprodend):
    prmtop = AmberPrmtopFile(parmFile)
    if simType == "explicit": system = prmtop.createSystem(nonbondedMethod=PME, nonbondedCutoff=nbCutoff*angstrom, constraints=HBonds)
    else: system = prmtop.createSystem(implicitSolvent=GBn2, implicitSolventKappa=1.0/nanometer, soluteDielectric=1.0, solventDielectric=78.5)
    set_dihedral_group(system)

    integrator = DualDeepLearningGaMDProduction(0.002*picoseconds, temperature*kelvins)
    isExist = os.path.exists("gamd-"+str(cycle)+".mdout")
    if isExist: os.remove("gamd-"+str(cycle)+".mdout")
    simulation = Simulation(prmtop.topology, system, integrator)

    if cycle == 0: simulation.loadState("equil.rst")
    else: simulation.loadState("gamd.rst")

    column_names = ["Parameters", "Values"]
    gamdRestart = pd.read_csv("gamd-restart.dat", names=column_names, header=0, delimiter="\t")
    boost_parameters = gamdRestart.Values.to_list()
    boost_parameters = np.array(boost_parameters)
    min_dihedral, max_dihedral = boost_parameters[1] * 4.184, boost_parameters[2] * 4.184
    min_total, max_total = boost_parameters[6] * 4.184, boost_parameters[7] * 4.184
    final_k0D, final_k0P = boost_parameters[5], boost_parameters[10]

    integrator.setGlobalVariableByName("VminD", min_dihedral)
    integrator.setGlobalVariableByName("VmaxD", max_dihedral)
    integrator.setGlobalVariableByName("Dihedralk0", final_k0D)
    integrator.setGlobalVariableByName("VminP", min_total)
    integrator.setGlobalVariableByName("VmaxP", max_total)
    integrator.setGlobalVariableByName("Totalk0", final_k0P)

    simulation.reporters.append(DCDReporter("gamd-"+str(cycle)+".dcd", prodRestartFreq))
    simulation.reporters.append(ExpandedStateDataReporter(system, "gamd-"+str(cycle)+".mdout", prodRestartFreq,
                                                    step=True, temperature=True,
                                                    brokenOutForceEnergies=True, potentialEnergy=True,
                                                    totalEnergy=True, density=True, separator="\t",
                                                    speed=True, remainingTime=True, totalSteps=ntprodpercyc))

    logFile = "gamd-"+str(cycle)+".log"
    isExist = os.path.exists(logFile)
    if isExist: os.remove(logFile)
    gamdLog = open(logFile, "w")
    gamdLog.write("# Gaussian accelerated Molecular Dynamics log file\n")
    gamdLog.write("# All energy terms are stored in unit of kcal/mol\n")
    gamdLog.write("# ntwx,total_nstep,Total-Energy,Dihedral-Energy,Total-Force-Weight,Dihedral-Force-Weight,"
              "Total-Boost,Dihedral-Boost,Total-Harmonic-Force-Constant,Dihedral-Harmonic-Force-Constant,"
              "Minimum-Total-Energy,Maximum-Total-Energy,Minimum-Dihedral-Energy,Maximum-Dihedral-Energy,"
              "Total-Reference-Energy,Dihedral-Reference-Energy\n")
    gamdLog.close()

    for step in np.arange(0, ntprodpercyc / prodRestartFreq):
        simulation.step(prodRestartFreq)
        simulation.saveState("gamd.rst")
        gamdLog = open(logFile, "a")
        gamdLog.write(str(prodRestartFreq) + "\t" + str(int((step + 1) * prodRestartFreq)) + "\t"
                      + str(integrator.getGlobalVariableByName("TotalEnergy") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("DihedralEnergy") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("TotalForceScalingFactor")) + "\t"
                      + str(integrator.getGlobalVariableByName("DihedralForceScalingFactor")) + "\t"
                      + str(integrator.getGlobalVariableByName("TotalBoostPotential") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("DihedralBoostPotential") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("Totalk0")) + "\t"
                      + str(integrator.getGlobalVariableByName("Dihedralk0")) + "\t"
                      + str(integrator.getGlobalVariableByName("VminP") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("VmaxP") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("VminD") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("VmaxD") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("TotalRefEnergy") / 4.184) + "\t"
                      + str(integrator.getGlobalVariableByName("DihedralRefEnergy") / 4.184) + "\n")
        gamdLog.close()

        isExist = os.path.exists("gamd-restart.dat")
        if isExist: os.remove("gamd-restart.dat")
        gamdRestart = open("gamd-restart.dat", "w")
        gamdRestart.write("#Parameters\tValues(kcal/mol)\n")
        gamdRestart.write("(0)Steps:\t" + str(int((step + 1)*prodRestartFreq)) + "\n")
        gamdRestart.write("(1)Boosted VminD:\t" + str(integrator.getGlobalVariableByName("VminD") / 4.184) + "\n")
        gamdRestart.write("(2)Boosted VmaxD:\t" + str(integrator.getGlobalVariableByName("VmaxD") / 4.184) + "\n")
        gamdRestart.write("(3)DihedralRefEnergy:\t" + str(integrator.getGlobalVariableByName("DihedralRefEnergy") / 4.184) + "\n")
        gamdRestart.write("(4)Final DihedralBoost:\t" + str(integrator.getGlobalVariableByName("DihedralBoostPotential") / 4.184) + "\n")
        gamdRestart.write("(5)Final k0D:\t" + str(integrator.getGlobalVariableByName("Dihedralk0")) + "\n")
        gamdRestart.write("(6)Boosted VminP:\t" + str(integrator.getGlobalVariableByName("VminP") / 4.184) + "\n")
        gamdRestart.write("(7)Boosted VmaxP:\t" + str(integrator.getGlobalVariableByName("VmaxP") / 4.184) + "\n")
        gamdRestart.write("(8)TotalRefEnergy:\t" + str(integrator.getGlobalVariableByName("TotalRefEnergy") / 4.184) + "\n")
        gamdRestart.write("(9)Final TotalBoost:\t" + str(integrator.getGlobalVariableByName("TotalBoostPotential") / 4.184) + "\n")
        gamdRestart.write("(10)Final k0P:\t" + str(integrator.getGlobalVariableByName("Totalk0")) + "\n")
        gamdRestart.close()
    
    os.system("scp -v gamd.rst gamd-"+str(cycle)+".rst")
    os.system("scp -v gamd-restart.dat gamd-"+str(cycle)+".restart.dat")
