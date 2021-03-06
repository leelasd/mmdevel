#!/usr/bin/env python
import sys
import argparse
import re

class AtomRecord:
    '''Represents a single atom.'''    
    def __init__(self, line):
        self.atomid = int(line[6:11])
        self.atomname = line[12:16].strip()
        self.resname = line[17:20].strip()
        self.chain = line[21]
        if self.chain == " ":
             self.chain = "X"
        # Solvent residue ids are frequently mangled
        # so just set the mangled ones to 0
        try:
            self.resid = int(line[22:26])
        except:
            self.resid = 0
        self.x = float(line[30:38])
        self.y = float(line[38:46])
        self.z = float(line[46:54])
        self.occupancy = float(line[54:60])
        self.tempfactor = float(line[60:66])
        
        self.ff_type = ''

class Molecule:

    solvent_residues = ["WAT", "T3P", "HOH", "PW", "W"]

    def __init__(self, filename):
        self.atoms = []
        self.load_from_pdb(filename)
        
    def load_from_pdb(self, filename):
        pdb = open(filename)
        for line in pdb:
            if line[0:6] == "ATOM  ":
                atom = AtomRecord(line)
                self.atoms.append(atom)
        print >>sys.stderr, "Read %d atoms from %s." % (len(self.atoms), filename)
        
    def nuke_solvent(self):
        print >>sys.stderr, "Stripping solvent residues."
        self.atoms = [atom for atom in self.atoms if atom.resname not in self.solvent_residues]

    def keep_only_atomname(self, atomname):
        '''Keeps only a certain type of atom. (e.g. CA, CB, N, ...)'''
        print >>sys.stderr, "Keeping only %s atoms." % atomname
        self.atoms = [atom for atom in self.atoms if atom.atomname == atomname]
        
    def print_as_psf(self):
        print "PSF CMAP"
        print ""
        print "       2 !NTITLE"
        print " REMARKS Generated by pdb_to_psf.py, by Tom Joseph <thomas.joseph@mssm.edu>"
        print " REMARKS Don't try MD with this, unless you're sure you know better than me"
        print ""
        print "%8d !NATOM" % len(self.atoms)
        
        for atom in self.atoms:
            print "%8d %-4s %4d %-4s %-4s %-4s %12.6f %10.4f 0" % \
                (atom.atomid, atom.chain, atom.resid, atom.resname, atom.atomname, \
                atom.ff_type, self.charges[atom.ff_type], 1.0)
        
        print "\n%8d !NBOND\n" % 0
        print "%8d !NTHETA\n" % 0
        print "%8d !NPHI\n" % 0
        print "%8d !NIMPHI\n" % 0
        print "%8d !NCRTERM\n" % 0
        
    def add_charmm_topology(self, top_filename):
        """Adds topology information taken from CHARMM top_whatever.rtf file."""
        
        nuke_comment_re = re.compile('!.*$') # Regexp to get rid of comments
        top = open(top_filename, "r")

        # Parse CHARMM topology file to extract the atom partial charges.
        # We are only interested in ATOM, BOND, DIHE cards
        # contained in blocks delimited by RESI cards.
        # Apparently CHARMM autogenerates dihedrals?
        current_residue = ""
        self.charge_by_type = {}
        bond_list = {}
        while True:
            l = top.readline()
            if l == "": break # EOF
            # Skip continuation line
            if l.strip().endswith('-'):
                top.readline()
                continue
            l = nuke_comment_re.sub('', l).strip()
            if l == "": continue # There could be nothing left after stripping out comment
            if l[0:4] == "RESI":
                current_residue = l.split()[1] # Failure here? Either a bug or corrupted top file
                self.charge_by_type[current_residue] = {}
                bond_list[current_residue] = {}
                # NTER and CTER specific atom charges
                self.charge_by_type[current_residue]['NH3'] = -0.30
                print >>sys.stderr, current_residue
            elif l[0:4] == "ATOM":
                (cardtype, atomname, atomtype, charge) = l.split()
                charge = float(charge)
                self.charge_by_type[current_residue][atomtype] = charge
            elif l[0:4] == "BOND":
                bonds = l.split()[1:]
                for i in range(0, len(bonds), 2):
                    # Order of atoms doesn't matter in a bond
                    key1 = bonds[i] + '-' + bonds[i+1]
                    key2 = bonds[i+1] + '-' + bonds[i]
                    bond_list[current_residue][key1] = True
                    bond_list[current_residue][key2] = True
        
        top.close()
        
        # TODO: Make a bond table
        print >>sys.stderr, "WARNING: No bond/angle/dihedral/improper information, yet!"
        print >>sys.stderr, self.charge_by_type
        
    def add_atom_types_from_itp(self, itp_filenames):
        if len(self.atoms) == 0:
            print >>sys.stderr, "BUG: Should have loaded atoms first"
            sys.exit(1)
            
        atom_i = 0
        self.charges = {}
            
        for filename in itp_filenames:
            in_atom_block, in_atomtypes_block = False, False
            in_ifdef_block = False
            itp = open(filename)
            for line in itp:
                line = line.strip()
                # If we see a section marker, assume it's not [ atoms ], until it actually is
                if line.startswith('[ atoms ]'):
                    in_atom_block = True
                    in_atomtypes_block = False
                    continue
                elif line.startswith('[ atomtypes ]'):
                    in_atomtypes_block = True
                    in_atom_block = False
                    continue
                elif line.startswith('[ '):
                    in_atom_block, in_atomtypes_block = False, False
                    continue
                elif line.startswith('#if'): # Skip ifdef blocks
                    in_ifdef_block = True
                    continue
                elif line.startswith('#endif'):
                    in_ifdef_block = False
                    continue
                elif line.startswith(';') or line == '': # Skip comment and blank lines entirely
                    continue
                    
                # Skip ifdef blocks!    
                if in_ifdef_block == True:
                    continue
                
                if in_atom_block == True:
                    toks = line.split()
                    (atomid, ff_type, resid, resname, atomname) = toks[0:5]
                    atomid, resid = int(atomid), int(resid)
                    if self.atoms[atom_i].resid != resid:
                        print >>sys.stderr, "WHOA! ITP mismatch: resid %d in PDB vs %d in ITP" % (self.atoms[atom_i].resid, resid)
                        sys.exit(1)
                    self.atoms[atom_i].ff_type = ff_type
                    atom_i += 1
                elif in_atomtypes_block == True:
                    toks = line.split()
                    try:
                        (ff_type, atomicnum, mass, charge, ptype, sigma, epsilon) = toks[0:7]
                        # Apparently here we can actually believe sigma and epsilon L-J parameters
                    except:
                        (ff_type, mass, charge, ptype, sigma, epsilon) = toks[0:6]
                    self.charges[ff_type] = float(charge)
                    # print >>sys.stderr, ff_type, float(charge)
                    
                    
        
if __name__ == "__main__":
    p = argparse.ArgumentParser(description='Creates barebones PSF file from PDB and optionally GROMACS ITP files')
    p.add_argument('pdb', help='PDB filename', default='molecule.pdb')
    p.add_argument('-k', '--keep-atom', help='Atom name to keep')
    p.add_argument('-g', '--gromacs-itp', help='GROMACS ITP file, if you want correct force field atom types (can specify this argument multiple times as necessary)', action='append')
    p.add_argument('-c', '--charmm-top', help='CHARMM top_whatever.rtf file, which is not well tested')
    args = p.parse_args()
    m = Molecule(args.pdb)
    if args.gromacs_itp is not None: m.add_atom_types_from_itp(args.gromacs_itp)
    if args.charmm_top is not None: m.add_charmm_topology(args.charmm_top)
    m.nuke_solvent()
    if args.keep_atom is not None: m.keep_only_atomname(args.keep_atom)
    
    # TODO: renumber atomids?, since we probably deleted a bunch of atoms
    
    m.print_as_psf()
