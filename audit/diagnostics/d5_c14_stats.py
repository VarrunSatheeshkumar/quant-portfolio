"""A18: SPY overnight series statistics under the C14 definition. Run from futures-public/."""
import sys, numpy as np; sys.path.insert(0, "."); from candidates import common as C
s = C.c14_series(); on = s.overnight*1e4
print("N", len(on), "mean bp", round(on.mean(),3), "block SE", round(C.block_se(on.values,on.index),4), "iid SE", round(on.std()/np.sqrt(len(on)),4), "lag1 autocorr", round(on.autocorr(1),3))
