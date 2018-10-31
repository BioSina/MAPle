'''
MAPle - Metagenomic Analysis PipeLine

@author: Sina Beier

This is the full MAPle pipeline for the analysis of paired-end short read metagenomic data
'''


import os
import sys
import re
import subprocess
from datetime import datetime
import shutil
import argparse

#Default variables, they will be set in the configuration file
variables = dict()
variables["FASTQC"] = "fastqc"
variables["gzip"] = "gzip"
variables["perl"] = "perl"
variables["prinseq"] = "prinseq-lite.pl"
variables["megan"] = "MEGAN"
variables["diamond"] = "diamond"
variables["malt"] = "malt-run"
variables["megantools"] = "tools"
variables["metaxa"] = "metaxa2"

variables["diamondindex"] = "diamond.dmnd"
variables["taxonomy"] = "acc2tax.abin"
variables["eggnog"] = "acc2eggnog.abin"
variables["interpro"] = "acc2interpro.abin"
variables["seed"] = "acc2seed.abin"


variables["trimwindow"] = 0
variables["trimqual"] = 0
variables["minlength"] = 0

variables["maxeval"] = 0.0
variables["minsupp"] = 0.0

variables["keepraw"] = True

variables["hostDB"] = "host"

variables["pairID1"] = ".1."
variables["pairID2"] = ".2."
variables["compressed"] = True

variables["malteval"] = 0.0
variables["maltsupp"] = 0.0
variables["maxeval"] = 0.0
variables["maltbase"] = "malt"


#Allow to name the analysis (name of logfile, mainly)
variables["name"] = "MAPle"

variables["raw2trimloss"] = 0.6
variables["rawabsolute"] = 10000

#Modules
variables["basic"] = True
variables["filterHost"] = False
variables["16S"] = False

global loghandle

#read in configuration file
def readConfig(config):
    print("Reading configuration file."),
    with open(config, 'rU') as c:
        print("."),
        for line in c:
            if (not(line.startswith("#")) and not(line == "\n")):
                l = re.sub("\n", "", line)
                split = re.split('\s=\s',l)
                variables[split[0]] = split[1]
    variables["pairID1pattern"] = re.escape(variables["pairID1"])
    variables["pairID2pattern"] = re.escape(variables["pairID2"])
    if variables["keepraw"] == "False":
        variables["keepraw"] = False
    else:
        variables["keepraw"] = True
    if variables["basic"] == "False":
        variables["basic"] = False
    else:
        variables["basic"] = True
    if variables["filterHost"] == "False":
        variables["filterHost"] = False
    else:
        variables["filterHost"] = True
    if variables["16S"] == "False":
        variables["16S"] = False
    else:
        variables["16S"] = True
        
    variables["rawabsolute"] = int(variables["rawabsolute"])
    variables["raw2trimloss"] = float(variables["raw2trimloss"])
    print(".")

#moving and subsequently renaming the raw files
def setupFiles(indir, outdir):
    print("Setting up input"),
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    global loghandle
    loghandle = open(outdir+"/"+variables["name"]+".log", 'w')
    loghandle.write(str(datetime.now())+": Started Setup\n")
    samples = list()
    os.chdir(outdir)
    if not os.path.exists(indir):
        sys.stderr.write("[FATAL ERROR] Please provide the correct input directory, including the fastq.gz files which were generated by your MiSeq run.")
        sys.exit(1)
    rawdir = "00_RAW"
    if not os.path.exists(os.getcwd()+"/"+rawdir):
        os.makedirs(os.getcwd()+"/"+rawdir)
    print("."),
    for i in os.listdir(indir):
        if ((i.endswith("fastq.gz"))or (i.endswith("fq.gz"))):
            if not(i.startswith("\_")):
                infile = indir+"/"+i
                if (re.search(variables["pairID1pattern"], i)):
                    sample = re.split(variables["pairID1pattern"], i)[0]
                else:
                    if (re.search(variables["pairID2pattern"], i)):
                        sample = re.split(variables["pairID2pattern"], i)[0]
                    else:
                        raise ValueError("Read pair identifiers cannot be detected.")
                if not(sample in samples):
                    samples.append(sample)
                    
                outfile = "00_RAW/"+i
                if variables["keepraw"]:
                    command = subprocess.Popen(['cp', infile, outfile])
                else:
                    command = subprocess.Popen(['mv', infile, outfile])
                command.wait()
        
        #else:
        #    raise ValueError("No valid compressed FastA files could be detected.")
    print("."),
    loghandle.write(str(datetime.now())+": Finished Setup successfully\n")
    print(".")
    return samples
            
#run FastQC on a given sample, either in paired or in single mode
def  fastqc(samplename, indir, mode ):
    file1 = ""
    file2 = ""
    loghandle.write(str(datetime.now())+": Started QC\n")
    if not os.path.exists(os.getcwd()+"/"+indir):
        sys.stderr.write("[FATAL ERROR] The directory on which you are running FastQC does not seem to exist. Please check file permissions and disk space.")
        sys.exit(1)
    fastqcdir = indir+"/fastqc"
    if not os.path.exists(os.getcwd()+"/"+fastqcdir):
        os.makedirs(os.getcwd()+"/"+fastqcdir)
    if mode=="paired":
        loghandle.write("Entering paired filter mode\n")
        for i in os.listdir(indir):
            if i.startswith(samplename+variables["pairID1"]):
                file1 = indir+"/"+i 
            if i.startswith(samplename+variables["pairID2"]):
                file2 = indir+"/"+i
        command = subprocess.Popen([variables["FASTQC"], '-noextract','-o',fastqcdir,file1,file2])
    else:
        for i in os.listdir(indir):
            if i.startswith(samplename):
                file1 = indir+"/"+i 
        command = subprocess.Popen([variables["FASTQC"],'-noextract','-o',fastqcdir,file1])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished QC successfully\n")

#Trimming paired reads with prinseq-lite
def trim(samplename, trimdir, rawdir):
    loghandle.write(str(datetime.now())+": Started trimming\n")
    if not os.path.exists(os.getcwd()+"/"+trimdir):
        os.makedirs(os.getcwd()+"/"+trimdir)
    tempdir = trimdir+"/temp"
    if not os.path.exists(os.getcwd()+"/"+tempdir):
        os.makedirs(os.getcwd()+"/"+tempdir)
    thedir = os.getcwd()+"/"+rawdir
    for i in os.listdir(thedir):
        temp = thedir+"/"+i
        if os.path.isfile(temp):
            if i.startswith(samplename+variables["pairID1"]):
                file1 = temp
            if i.startswith(samplename+variables["pairID2"]):
                file2 = temp
    if variables["compressed"]:
        outfile1 = open(tempdir+"/"+samplename+".fastq", 'w')
        command = subprocess.Popen([variables["gzip"],'-dc', file1], stdout=subprocess.PIPE)
        outfile1.writelines(command.stdout)
        command.wait()
        outfile1.close()
    
        outfile1 = open(tempdir+"/"+samplename+variables["pairID1"]+".fastq", 'w')
        command = subprocess.Popen([variables["gzip"],'-dc', file1], stdout=subprocess.PIPE)
        outfile1.writelines(command.stdout)
        command.wait()
        outfile1.close()
        outfile2 = open(tempdir+"/"+samplename+variables["pairID2"]+".fastq", 'w')
        command = subprocess.Popen([variables["gzip"],'-dc', file2], stdout=subprocess.PIPE)
        outfile2.writelines(command.stdout)
        command.wait()
        outfile2.close()
    else:
        #copy original files to tempfile, temp directory will be removed afterwards
        command = subprocess.Popen(['cp', file1, tempdir+"/"+samplename+variables["pairID1"]+".fastq"])
        command = subprocess.Popen(['cp', file2, tempdir+"/"+samplename+variables["pairID2"]+".fastq"])
        

    command = subprocess.Popen([variables["perl"], variables["prinseq"], '-fastq',tempdir+"/"+samplename+variables["pairID1"]+".fastq", '-fastq2',tempdir+"/"+samplename+variables["pairID2"]+".fastq", '-log',trimdir+"/"+samplename+".log", '-trim_qual_window',str(variables["trimwindow"]), '-trim_qual_right',str(variables["trimqual"]),
                               '-trim_left',str(variables["lefttrim"]), '-out_good',trimdir+"/"+samplename+".trim.good", '-out_bad',trimdir+"/"+samplename+".trim.bad"])
    command.wait()
    newname = samplename+".trimmed"+variables["pairID1"]+"fastq"
    outfile = trimdir+"/"+newname
    infile = trimdir+"/"+samplename+".trim.good_2.fastq"
    command = subprocess.Popen(['mv',infile, outfile])
    command.wait()
    newname = samplename+".trimmed"+variables["pairID2"]+"fastq"
    outfile = trimdir+"/"+newname
    infile = trimdir+"/"+samplename+".trim.good_1.fastq"
    command = subprocess.Popen(['mv',infile, outfile])
    command.wait()

    
    shutil.rmtree(os.getcwd()+"/"+tempdir)
    loghandle.write(str(datetime.now())+": Finished trimming successfully\n")

#Filtering out contaminants or host sequences with MALT
def filterHost(samplename, filtereddir, trimmeddir):
    loghandle.write(str(datetime.now())+": Started filtering host reads\n")
    if not os.path.exists(os.getcwd()+"/"+filtereddir):
        os.makedirs(os.getcwd()+"/"+filtereddir)
        c = subprocess.Popen(['chmod', '-R','777',os.getcwd()+"/"+filtereddir])
        c.wait()
    infile = trimmeddir+"/"+samplename+".trimmed"+variables["pairID1"]+"fastq"
    rmafile = filtereddir+"/"+samplename+".temp"+variables["pairID1"]+"rma"
    outfile = filtereddir+"/"+samplename+".filtered"+variables["pairID1"]+"fasta"
    hostfile = filtereddir+"/"+samplename+".host"+variables["pairID1"]+"fasta"
    command = subprocess.Popen([variables["malt"],'-v' , '-m', 'BlastN', '-at', 'SemiGlobal','-t','30','-mem', "page",'-id','75.00','-supp',str(variables["minsupp"]),'-e', str(variables["maxeval"]), '-i',infile,'-d',variables["hostDB"],'-o',rmafile,'-ou', outfile, '-oa', hostfile])
    command.wait()
    infile = trimmeddir+"/"+samplename+".trimmed"+variables["pairID2"]+"fastq"
    rmafile = filtereddir+"/"+samplename+".temp"+variables["pairID2"]+"rma"
    outfile = filtereddir+"/"+samplename+".filtered"+variables["pairID2"]+"fasta"
    hostfile = filtereddir+"/"+samplename+".host"+variables["pairID2"]+"fasta"
    command = subprocess.Popen([variables["malt"], '-m', 'BlastN', '-at', 'SemiGlobal','-t','30','-mem', "page",'-id','75.00','-supp',str(variables["minsupp"]),'-e', str(variables["maxeval"]), '-i',infile,'-d',variables["hostDB"],'-o',rmafile,'-ou', outfile, '-oa', hostfile])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished filtering host reads successfully\n")
    

#Running Diamond on non-host sequences extracted from host filtering (they are fastA)
def diamondFasta(samplename, aligneddir, filtereddir):
    loghandle.write(str(datetime.now())+": Started alignment of non-host reads \n")
    if not os.path.exists(os.getcwd()+"/"+aligneddir):
        os.makedirs(os.getcwd()+"/"+aligneddir)
        c = subprocess.Popen(['chmod', '-R','777',os.getcwd()+"/"+aligneddir])
        c.wait()
    precommand = variables["diamond"]+" blastx -p 30 -d "+variables["diamondindex"]+" -a "+aligneddir+"/"+samplename+variables["pairID1"]+"daa -q "+filtereddir+"/"+samplename+".filtered"+variables["pairID1"]+"fasta.gz"
    command = subprocess.Popen(precommand.split())
    command.wait()
    precommand = variables["diamond"]+" blastx -p 30 -d "+variables["diamondindex"]+" -a "+aligneddir+"/"+samplename+variables["pairID2"]+"daa -q "+filtereddir+"/"+samplename+".filtered"+variables["pairID2"]+"fasta.gz"
    command = subprocess.Popen(precommand.split())
    command.wait()
    loghandle.write(str(datetime.now())+": Finished alignment of non-host reads successfully\n")


#Running Diamond on trimmed fastQ files from unfiltered sequences    
def diamond(samplename, aligneddir, trimmeddir):
    loghandle.write(str(datetime.now())+": Started alignment of trimmed reads \n")
    if not os.path.exists(os.getcwd()+"/"+aligneddir):
        os.makedirs(os.getcwd()+"/"+aligneddir)
        c = subprocess.Popen(['chmod', '-R','777',os.getcwd()+"/"+aligneddir])
        c.wait()
    precommand = variables["diamond"]+" blastx -p 30 -d "+variables["diamondindex"]+" -a "+aligneddir+"/"+samplename+variables["pairID1"]+"daa -q "+trimmeddir+"/"+samplename+".trimmed"+variables["pairID1"]+"fastq"
    command = subprocess.Popen(precommand.split())
    command.wait()
    precommand = variables["diamond"]+" blastx -p 30 -d "+variables["diamondindex"]+" -a "+aligneddir+"/"+samplename+variables["pairID2"]+"daa -q "+trimmeddir+"/"+samplename+".trimmed"+variables["pairID2"]+"fastq"
    command = subprocess.Popen(precommand.split())
    command.wait()
    loghandle.write(str(datetime.now())+": Finished alignment of trimmed reads successfully\n")
   
def daa2rma(samplename, megandir, aligneddir):
    loghandle.write(str(datetime.now())+": Started generating RMA file\n")
    if not os.path.exists(os.getcwd()+"/"+megandir):
        os.makedirs(os.getcwd()+"/"+megandir)
        c = subprocess.Popen(['chmod', '-R','777',os.getcwd()+"/"+megandir])
        c.wait()
    precommand = variables["megantools"]+"/daa2rma -i "+aligneddir+"/"+samplename+variables["pairID1"]+"daa "+aligneddir+"/"+samplename+variables["pairID2"]+"daa -o "+megandir+"/"+samplename+".rma6 -p true -a2t "+variables["taxonomy"]+" -a2interpro2go "+variables["interpro"]+" -a2eggnog "+variables["eggnog"]+" -a2seed "+variables["seed"]+" -me "+variables["maxeval"]+" -supp "+variables["minsupp"]
    command = subprocess.Popen(precommand.split())
    command.wait()
    loghandle.write(str(datetime.now())+": Finished generating RMA file successfully\n")

#select 16S reads
def select16S(samplename, filterdir, trimdir):
    loghandle.write(str(datetime.now())+": Started selecting 16S reads\n")
    if not os.path.exists(os.getcwd()+"/"+filterdir):
        os.makedirs(os.getcwd()+"/"+filterdir)
    precommand = variables["metaxa"]+" -o "+filterdir+"/"+samplename+" -1 "+trimdir+"/"+samplename+".trimmed"+variables["pairID1"]+"fastq"+" -2 "+trimdir+"/"+samplename+".trimmed"+variables["pairID2"]+"fastq -f q -x T --cpu 20"
    command = subprocess.Popen(precommand.split())
    command.wait()
    loghandle.write(str(datetime.now())+": Finished selecting 16S reads successfully\n")

#Align and classify selected 16S sequences
def malt(samplename, aligneddir, filterdir):
    loghandle.write(str(datetime.now())+": Started alignment of 16S reads\n")
    if not os.path.exists(os.getcwd()+"/"+aligneddir):
        os.makedirs(os.getcwd()+"/"+aligneddir)
        
    infile = filterdir+"/"+samplename+".extraction.fasta"
    outfile =aligneddir+"/"+samplename+".rma"
    command = subprocess.Popen([variables["malt"], '-m', 'BlastN', '-at', 'SemiGlobal','-t','20','-rqc','true','-supp',str(variables["maltsupp"]),'-e', str(variables["malteval"]), '-mpi', str(75.0),'-top', str(10.0),'-i',infile,'-d',variables["maltbase"], '-o',outfile])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished alignment of 16S reads successfully\n")

#read in Quality Control results for breakpoints
def readQC(samplename, indi ,mode):
    indir = os.getcwd()+"/"+indi
    pair = True
    file1 = ""
    file2 = ""
    #set pair according to mode and "paired"/not
    #modes are raw, trimmed, filtered (filtered is always not a paired mode)
    if (mode=="filtered"):
        pair = False
    else:
        pair = True
        
    if pair:
        short1 = variables["pairID1"][:-1]
        print(short1)
        short2 = variables["pairID2"][:-1]
        for i in os.listdir(indir+"/fastqc/"):
            print(i)
            if (i.startswith(samplename+short1) and i.endswith('zip')):
                file1 = indir+"/fastqc/"+i 
            if (i.startswith(samplename+short2) and i.endswith('zip')):
                file2 = indir+"/fastqc/"+i 
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file1])
        command.wait()
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file2])
        command.wait()
        print(file1)
        sub1 = re.sub("\.zip","", file1)
        print(sub1)
        filename1 = sub1+"/fastqc_data.txt"
        sub2 = re.sub("\.zip","", file2)
        filename2 = sub2+"/fastqc_data.txt"
        tuple1 = fastqcData(filename1)
        tuple2 = fastqcData(filename2)
        
        #for now, return tuple2
        return tuple2
    else:
        for i in os.listdir(indir+"/fastqc/"):
            if (i.startswith(samplename) and i.endswith('zip')):
                file1 = indir+"/fastqc/"+i 
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file1])
        command.wait()
        sub = re.sub("\.zip","", file1)
        filename1 = sub+"/fastqc_data.txt"
        tuple1 = fastqcData(filename1)
        return tuple1
       
        
#read a file from FastQC      
def fastqcData(qcdata):
    mini = 0
    maxi = 0
    num = 0
    with open(qcdata, 'rU') as qc:
        for line in qc:
            line = re.sub('\n', "", line)
            #number of sequences
            if (line.startswith("Total Sequences")):
                s = re.split('\t', line)
                num = s[-1]
            #min/max length
            if (line.startswith("Sequence length")):
                s = re.split('\t', line)
                tmp = s[-1]
                if re.search("-", tmp):
                    split = re.split("-", tmp)
                    mini = split[0]
                    maxi = split[1]
                else:
                    mini = tmp
                    maxi = tmp
    
    result = mini, maxi, num
    return result
    

#run full analysis    
def runAnalysis(indir, outdir, config):
    global logfile
    readConfig(config)
    samples = setupFiles(indir, outdir)
    for s in samples:
        #always run preprocessing
        fastqc(s, "00_RAW", "paired")
        t1 = readQC(s, "00_RAW", "raw")
        if int(t1[2])< variables["rawabsolute"]:
            loghandle.write("Breakpoint: Raw QC for sample "+s+" failed with a read count of only "+t1[2]+"\n")
            continue
        loghandle.write("Raw QC for sample: "+s+" (based on R2)\n")
        loghandle.write("Minimal read length: "+t1[0]+", maximal read length: "+t1[1]+", number of reads: "+t1[2]+"\n")
        trim(s, "01_trimmed", "00_RAW")
        fastqc(s+".trimmed", "01_trimmed", "paired")
        t2 = readQC(s+".trimmed", "01_trimmed", "trimmed")
        raw2trimloss = 1.0-(float(t2[2])/float(t1[2]))
        if raw2trimloss > variables["raw2trimloss"]:
            loghandle.write("Breakpoint: Trimmed QC for sample "+s+" failed with a loss of "+str(raw2trimloss)+" compared to raw read counts\n")

            continue
        loghandle.write("Trimmed QC for sample: "+s+" (based on R2) \n")
        loghandle.write("Minimal read length: "+t2[0]+", maximal read length: "+t2[1]+", number of reads: "+t2[2]+"\n")
        
        #run the different modules
        #Basic Metagenomics
        if (variables["basic"]):
            diamond(s,"02_basic_aligned", "01_trimmed")
            daa2rma(s, "03_basic_megan", "02_basic_aligned")
        #Host-Associated Data
        if (variables["filterHost"]):
            filterHost(s, "02_host_filtered", "01_trimmed")
            diamondFasta(s,"03_host_aligned", "02_host_filtered")
            daa2rma(s, "04_host_megan", "03_host_aligned")
        #Taxonomic Analysis
        if (variables["16S"]):
            select16S(s,"02_16S_selected", "01_trimmed")
            malt(s,"03_16S_aligned", "02_16S_selected") 
        
        

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description = "MAPle - Metagenomic Analysis PipeLinE", 
                                     epilog= "For more information please read the MAPle manual, report bugs and problems to sina.beier@uni-tuebingen.de")
    parser.add_argument("indirectory", type=str, help='''Input directory''')
    parser.add_argument("outdirectory", type=str, help='''Output directory (script will put renamed raw files in this directory and generate all the output here)''')
    parser.add_argument("config", type=str, help='''Config file including paths to tools and parameters.''')

    args = parser.parse_args()
    runAnalysis(args.indirectory, args.outdirectory, args.config)
