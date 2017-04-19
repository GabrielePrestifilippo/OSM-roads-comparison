#!/usr/bin/env python 
#  -*- coding:utf-8 -*-
############################################################################## 
# MODULE:    v.osm.preproc
# AUTHOR(S): Monia Molinari, Marco Minghini
# PURPOSE:   Tool for extracting road features in the OSM dataset which have a correspondence in the reference dataset
# COPYRIGHT: (C) 2015 by the GRASS Development Team 
# 
# This program is free software under the GNU General Public 
# License (>=v2). Read the file COPYING that comes with GRASS 
# for details. 
# ############################################################################
#%Module
#%  description: Tool for extracting road features in the OSM dataset which have a correspondence in the reference dataset
#%  keywords: vector, OSM, preprocessing
#%End

#%option 
#% key: osm
#% type: string 
#% gisprompt: old,vector,vector
#% description: OpenStreetMap dataset
#% required: yes 
#%end

#%option 
#% key: ref
#% type: string 
#% gisprompt: old,vector,input
#% description: Reference dataset
#% required: yes
#%end

#%option 
#% key: buffer
#% type: double 
#% description: Buffer around reference dataset (map units)
#% required: yes
#%end

#%option 
#% key: angle_thres
#% type: double 
#% description: Threshold value for angular coefficient comparison (degrees)
#% required: yes
#%end

#%option G_OPT_V_OUTPUT
#% key: output
#% description: Name for output map
#% required: yes
#%end

#%option 
#% key: douglas_thres
#% type: double 
#% description: Threshold value for Douglas-Peucker algorithm (map unit)
#% required: no
#%end

#%option G_OPT_F_OUTPUT
#% key: out_file
#% description: Name for output file with statistics (if omitted or "-" output to stdout)
#% required: no
#%end

import math
import sys
import shutil
import time
import grass.script as grass

def length(data):
    feat_osm = int(((grass.read_command("v.info", map=data,flags="t",quiet=True)).split("\n")[2]).split("=")[1])
    if feat_osm>0:
        length_data = grass.read_command("v.to.db",map=data,option="length",flags="p")
        s_data=0 
        l_data = length_data.split("\n")
        for item in l_data[1:-1]:
            s_data+=float(item.split("|")[1])         
    else:
        s_data=0
    return s_data


def GetCoeff(vect):
    coord_start = grass.read_command("v.to.db", map=vect, option="start", type="line",flags="p").split("\n")[1]
    x_start = float(coord_start.split("|")[1])
    y_start = float(coord_start.split("|")[2])
    coord_end = grass.read_command("v.to.db", map=vect, option="end", type="line",flags="p").split("\n")[1]   
    x_end = float(coord_end.split("|")[1])
    y_end = float(coord_end.split("|")[2])
    if (x_end-x_start) <> 0:
        m = (y_end-y_start)/(x_end-x_start)
    else:
        m = 10**9
    return m

def main():
    osm = options["osm"]
    ref =  options["ref"]
    bf = options["buffer"]
    angle_thres = options["angle_thres"]
    doug = options["douglas_thres"]
    out = options["output"]
    out_file =  options["out_file"]

    ## Check if input files exist
    if not grass.find_file(name=osm,element='vector')['file']:
        grass.fatal(_("Vector map <%s> not found") % osm)

    if not grass.find_file(name=ref,element='vector')['file']:
        grass.fatal(_("Vector map <%s> not found") % ref)

    ## Prepare temporary map names
    processid = str(time.time()).replace(".","_")
    ref_gen = "ref_gen_" + processid
    ref_split = "ref_split_" + processid
    osm_split = "osm_split_" + processid
    deg_points = "deg_points_" + processid
    degmin_points = "degmin_points_" + processid
    ref_degmin = "ref_degmin_" + processid
    patch = "patch_" + processid
    fdata = "fdata_" + processid
    fbuffer = "fbuffer_" + processid
    odata = "odata_" + processid
    osdata = "osdata_" + processid
    outbuff = "outbuff_" + processid

    ## Calculate length original data
    l_osm = length(osm)
    l_ref = length(ref)

    if l_ref == 0:
        grass.run_command("g.remove", type="vect", pattern="%s"%processid,flags="fr",quiet=True)
        grass.fatal(_("No reference data for comparison"))

    if l_osm == 0:
        grass.run_command("g.remove", type="vect", pattern="%s"%processid,flags="fr",quiet=True)
        grass.fatal(_("No OSM data for comparison"))


    ## Generalize
    if doug:
        grass.run_command("v.generalize",input=ref,output=ref_gen,method="douglas", threshold=doug,quiet=True)
        ref = ref_gen

    ## Split REF datasets
    grass.run_command("v.split",input=ref,output=ref_split,vertices=2,quiet=True)   
    grass.run_command("v.out.ogr",input=ref_split,output="/tmp/%s"%ref_split,flags="s",quiet=True)
    grass.run_command("g.remove",type="vect",name=ref_split,flags="f",quiet=True)
    grass.run_command("v.in.ogr",input="/tmp/%s/%s.shp"%(ref_split,ref_split),output=ref_split,quiet=True)
    ref = ref_split
    shutil.rmtree('/tmp/%s/'%ref_split)

    ## Split OSM datasets
    grass.run_command("v.split",input=osm,output=osm_split,vertices=2,quiet=True)
    grass.run_command("v.out.ogr",input=osm_split,output="/tmp/%s"%osm_split,flags="s",quiet=True)
    grass.run_command("g.remove",type="vect",name=osm_split,flags="f",quiet=True)
    grass.run_command("v.in.ogr",input="/tmp/%s/%s.shp"%(osm_split,osm_split),output=osm_split,quiet=True)
    osm_orig = osm
    osm = osm_split
    shutil.rmtree('/tmp/%s/'%osm_split)

    # Calculate degree and extract REF category lines intersecting points with minimum value
    grass.run_command("v.net.centrality",input=ref, output=deg_points, degree="degree",flags="a",quiet=True)
    list_values = (grass.read_command("v.db.select",map=deg_points,columns="degree",flags="c",quiet=True)).split("\n")[0:-1]
    degmin = min(map(float,list_values))
 
    grass.run_command("v.extract", input=deg_points, output=degmin_points, where="degree=%s"%degmin,quiet=True)
    grass.run_command("v.select",ainput=ref,binput=degmin_points,output=ref_degmin,operator="overlap",quiet=True)
    list_lines = (grass.read_command("v.db.select",map=ref_degmin,columns="cat",flags="c",quiet=True)).split("\n")[0:-1]
    #print list_lines
  
    ## Create new vector map
    grass.run_command("v.edit",map=patch+"_0_0",tool="create",quiet=True)
    
    list_feature = grass.read_command("v.db.select",map=ref,columns="cat",flags="c",quiet=True).split("\n")[0:-1]
    i=0
    z=0
    #print list_feature

    ## Angular coefficient Comparison
    for f in list_feature:
        grass.run_command("v.extract",input=ref,output=fdata+"_%s"%f,where="cat=%s"%f,overwrite=True,quiet=True) 
        if f in list_lines:
            grass.run_command("v.buffer",input=fdata+"_%s"%f,output=fbuffer+"_%s"%f,flags="c",distance=bf,overwrite=True,quiet=True)
        else:
            grass.run_command("v.buffer",input=fdata+"_%s"%f,output=fbuffer+"_%s"%f,distance=bf,overwrite=True,quiet=True)

        grass.run_command("v.overlay",ainput=osm, atype="line",binput=fbuffer+"_%s"%f,output=odata+"_%s"%f,operator="and",overwrite=True,quiet=True)
        lines = ((grass.read_command("v.info", map=odata+"_%s"%f,flags="t",quiet=True)).split("\n")[2]).split("=")[1]
        if int(lines)==0:
            grass.run_command("g.remove", type="vect", name="%s_%s,%s_%s,%s_%s"%(fdata,f,fbuffer,f,odata,f),flags="f",quiet=True)
        else:
            ## Get REF angular coefficient
            list_subfeature = grass.read_command("v.db.select",map=odata+"_%s"%f,columns="cat",flags="c",quiet=True).split("\n")[0:-1]
            m_ref = GetCoeff(fdata+"_%s"%f)
            #print m_ref

            ## Get OSM subfeatures angular coefficient
            for sf in list_subfeature:    
                grass.run_command("v.extract",input=odata+"_%s"%f,output=osdata+"_%s_%s"%(f,sf),where="cat=%s"%sf,overwrite=True,quiet=True) 
                m_osm = GetCoeff(osdata+"_%s_%s"%(f,sf))
    
                     
                if math.degrees(abs(math.atan((m_ref-m_osm)/(1+m_ref*m_osm))))<=angle_thres:
                    grass.run_command("v.patch",input="%s_%s_%s,%s_%s_%s"%(patch,i,z,osdata,f,sf),output=patch+"_%s_%s"%(f,sf),overwrite=True,quiet=True)
                    grass.run_command("g.remove", type="vect", name="%s_%s_%s,%s_%s_%s"%(patch,i,z,osdata,f,sf), flags="f",quiet=True)
                    i=f
                    z=sf
                else:
                    grass.run_command("g.remove", type="vect", name=osdata+"_%s_%s"%(f,sf), flags="f",quiet=True)
            grass.run_command("g.remove", type="vect", name="%s_%s,%s_%s,%s_%s"%(fdata,f,fbuffer,f,odata,f), flags="f",quiet=True)

    ## Clean output map
    l_map = grass.read_command("g.list",type="vect",quiet=True).split("\n")[0:-1]
    last_map = [s for s in l_map if "patch" in s]
    grass.run_command("v.buffer", input=last_map[0],output=outbuff, distance=0.0001,quiet=True)
    grass.run_command("v.overlay",ainput=osm_orig,atype="line",binput=outbuff,output=out,operator="and",flags="t",quiet=True)

    ## Delete all maps
    grass.run_command("g.remove",type="vect",name="%s,%s,%s,%s,%s,%s,%s"%(deg_points,ref_degmin,degmin_points,ref_gen,ref_split,osm_split,outbuff),flags="f",quiet=True)

    grass.run_command("g.remove",type="vect",name="%s"%last_map[0],flags="f",quiet=True)

    ## Calculate final map statistics
    l_osm_proc = length(out)
    diff_osm = l_osm - l_osm_proc
    diff_p_osm = diff_osm/l_osm*100
    diff_new = l_ref - l_osm_proc
    diff_p_new = diff_new/l_ref*100

    ##  Write output file with statistics (if required)
    if len(out_file)>0:
        fil=open(out_file,"w")
        fil.write("REF dataset length: %s m\n"%(round(l_ref,1)))
        fil.write("Original OSM dataset length: %s m\n"%(round(l_osm,1)))
        fil.write("Processed OSM dataset length: %s m\n"%(round(l_osm_proc,1)))
        fil.write("Difference between OSM original and processed datasets length: %s m (%s%%)\n"%(round(diff_osm,1),round(diff_p_osm,1)))      
        fil.write("Difference between REF dataset and processed OSM dataset length: %s m (%s%%)\n"%(round(diff_new,1),round(diff_p_new,1)))   
        fil.close()   

    ## Print statistics
    print("#####################################################################\n")
    print("Original OSM dataset length: %s m\n"%(round(l_osm,1)))
    print("Processed OSM dataset length: %s m\n"%(round(l_osm_proc,1)))
    print("Difference between OSM original and processed datasets length: %s m (%s%%)\n"%(round(diff_osm,1),round(diff_p_osm,1)))
    print("Difference between REF dataset and processed OSM dataset length: %s m (%s%%)\n"%(round(diff_new,1),round(diff_p_new,1)))
    print("#####################################################################\n")
    


if __name__ == "__main__":
    options,flags = grass.parser()
    sys.exit(main())
    
