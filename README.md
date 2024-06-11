Check it WHILE you can (ciwyc - "sci-vic")
==========================================
ECS 289C Project: Different encoundings for bounded model checking
------------------------------------------------------------------

This project defines a toy progamming language (WHILE, see ciwyc/while_parsing.py)
and explores serveral techniques of symbollicaly representing it's transition system
(i.e. it's unrolled program graph).


Setup
=====

This project requires python3.12 and the pip packages in requirements.txt.  
You can install them using:
```bash
pip3 install -r requirements.txt
```
You can use [mise](https://github.com/jdx/mise) to install the right python version and create a
vitual environment automatically.

Usage
=====

For usage see:
```bash
python3 src/compare_encodings.py -h
python3 src/transition_system.py -h
python3 src/while_parsing.py -h
```

Tests
=====

To run the tests call pytest in the project root (admittedly the test converage is bad).
