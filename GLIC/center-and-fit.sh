#!/bin/bash
i=$1
inp="1
0"
echo $inp | trjconv -s $i.tpr -f $i.xtc -o $i.1.tmp.xtc -pbc nojump -ur compact -center
echo $inp | trjconv -s $i.tpr -f $i.1.tmp.xtc -o $i.2.tmp.xtc -fit rot+trans
echo $inp | trjconv -s $i.tpr -f $i.2.tmp.xtc -o $i.nopbc.fit.xtc -pbc mol -ur compact -center
rm -f $i.1.tmp.xtc $i.2.tmp.xtc
