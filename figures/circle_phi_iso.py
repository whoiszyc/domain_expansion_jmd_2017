"""
Active learning using ALBL and the GPC as classifier

Author(s): Wei Chen (wchen459@umd.edu)

References:
-----------
Hsu, W. N., & Lin, H. T. (2015, January). Active learning by learning. In Proceedings 
of the Twenty-Ninth AAAI Conference on Artificial Intelligence (pp. 2659-2665). AAAI Press.
"""

import math
import numpy as np
from sklearn.neighbors import KernelDensity
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.gaussian_process.kernels import RBF
from sklearn.metrics import f1_score
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
import matplotlib.patches as patches
from scipy.stats import norm
from scipy.optimize import differential_evolution
import numdifftools as nd
from libact.base.dataset import Dataset
from libact.query_strategies import RandomSampling
import matplotlib.mlab as mlab
from matplotlib import rcParams
rcParams.update({'font.size': 20})

import sys
sys.path.insert(0, '..')
from al_models import GPC, GPR
from query_strategies import UncertSampling, AdversarialSampling


fontsize = 40

    
def get_label(D, landmark, threshold):
    
    L = (np.min(pairwise_distances(D, landmark), axis=1) < threshold)
    L = L*2-1
    return L
    
def gen_samples(d, bounds, density=400):
    
    r = bounds[1,:] - bounds[0,:]
    N = int(density * r[0] * r[1])
    samples = np.random.rand(N, d)
    samples = samples * r.reshape(1, d) + bounds[0,:].reshape(1, d)
    
    return samples
    
def expand_pool(D, bounds_old, expansion_rate):
    
    d = D.shape[1]

    # Expand the previous query boundary based on D
    bounds_new = np.zeros_like(bounds_old)
    bounds_new[0,:] = np.min(D, axis=0) - expansion_rate
    bounds_new[1,:] = np.max(D, axis=0) + expansion_rate
    
    # Generate samples inside the new boundary
    pool = gen_samples(d, bounds_new)
    
    # Exclude samples inside the old boundary
    indices = np.logical_or(pool[:,0] < bounds_old[0,0], pool[:,0] > bounds_old[1,0])
    indices = np.logical_or(indices, pool[:,1] < bounds_old[0,1])
    indices = np.logical_or(indices, pool[:,1] > bounds_old[1,1])
    pool = pool[indices]
    print pool.shape[0]
    
    return pool, bounds_new
    
def plot_gaussian(mu, sigma, epsilon, j):
    
    import matplotlib 
    matplotlib.rc('xtick', labelsize=fontsize) 
    matplotlib.rc('ytick', labelsize=fontsize)
    
    y_hat = mu/np.abs(mu)
    x = np.linspace(-3.5+mu, 3.5+mu, 10000)
    y = mlab.normpdf(x, mu, sigma)
    
    plt.figure(figsize=(15,8), tight_layout=True)
    ax2 = plt.subplot(111)
    plt.plot(x, y)
    ax2.annotate(r'$f=\bar{f}$', xy=(mu-.5, .62), xytext=(mu-.5, .62), fontsize=fontsize)
    if epsilon > 0:
        plt.annotate('', xy=(epsilon, .1), xycoords='data',
                        xytext=(0, .1), textcoords='data',
                        arrowprops={'arrowstyle': '<->'})
        ax2.annotate(r'$\epsilon$', xy=(epsilon, 0), xytext=(epsilon/2-.1, .06), fontsize=fontsize)
    ax2.annotate(r'$\mathcal{N}(\bar{f}, \Sigma)$', xy=(1.5, .3), xytext=(1.5, .3), fontsize=fontsize)
    plt.axvline(x=mu, c='g')
    plt.axvline(x=0, c='g', ls='--')
    ax2.fill_between(x, 0, y, where=-y_hat*x>epsilon)
    plt.xlabel(r'$f$', fontsize=fontsize)
    plt.ylim(0,.7)
    plt.xlim(-3.5,3.5)
    plt.title(r'Point %d ($\epsilon$=%.1f)' % (j, epsilon), fontsize=fontsize)
#    plt.ylabel('Probability density', fontsize=20)
#    plt.title(r'$\hat{y} = -1$', fontsize=fontsize)
        
    
if __name__ == "__main__":
    
    n_iter = 35
    d = 2
    expansion_rate = 1.5
    margin = .7 # higher -> emphasize more on variance -> more exploration/less exploit
    
    # Set a global boundary
    BD = np.array([[-2.2, -4], 
                   [6.8, 5]])
    
    # Create experimental dataset
    landmark = np.array([[2, 0]])
        
    # Initial labeled samples
    np.random.seed(0)
    D0 = np.random.rand(5, d)
    D = D0
    threshold = 1.5
    L = get_label(D, landmark, threshold)
    print L
    dataset = Dataset(D, L)
    
    # Generate test set
    D_test = gen_samples(d, BD, density=10)
    L_test = get_label(D_test, landmark, threshold)
    testset = Dataset(D_test, L_test)
    
    sigma = np.mean(pairwise_distances(D0))
    
    qs = AdversarialSampling(
         dataset, # Dataset object
         model=GPC(RBF(1), optimizer=None),
         margin=margin
         )
    
    qs1 = UncertSampling(                    
          dataset, # Dataset object
          model=GPC(RBF(1), optimizer=None),
          method='sm'
          )
    
    qs2 = RandomSampling(dataset)

    center0 = np.mean(D[L==1], axis=0)
    center = center0
    bounds_old = np.vstack((np.min(D0, axis=0), np.max(D0, axis=0)))
    i = 0
    clf = GPC(RBF(1), optimizer=None)
    plt.figure(figsize=(16, 8))
                    
    while i < n_iter+1:
        
        print 'Iteration: %d/%d' %(i, n_iter)
        
        # Generate a pool and expand dataset
        pool, bounds_new = expand_pool(D, bounds_old, expansion_rate)
        for entry in pool:
            dataset.append(entry)
        
        # Query a new sample
        ask_id, clf = qs.make_query(center, margin)
#        ask_id, clf = qs1.make_query()
#        ask_id = qs2.make_query()
#        clf.train(dataset)
        new = dataset.data[ask_id][0].reshape(1,-1)
        
        if i == 14 or i == 35:
    
            # Create a mesh grid
            xx, yy = np.meshgrid(np.linspace(BD[0][0], BD[1][0], 500),
                                 np.linspace(BD[0][1], BD[1][1], 500))
            
            # Plot the decision function for each datapoint on the grid
            grid = np.vstack((xx.ravel(), yy.ravel())).T
            Z0 = clf.predict_real(grid)[:,-1] # to show probability
            Z0 = Z0.reshape(xx.shape)
            Z1, Z4 = clf.predict_mean_var(grid) # to show posterior mean and variance
            Z1 = Z1.reshape(xx.shape)
            Z4 = Z4.reshape(xx.shape)
            b = clf.get_kernel().get_params()['length_scale']
            Z2 = norm.cdf(-(np.abs(Z1)+margin)/b, 0, np.sqrt(Z4)) # to show query boundary
            Z2 = Z2.reshape(xx.shape)
            Z3 = get_label(grid, landmark, threshold) # to show ground truth decision boundary
            Z3 = Z3.reshape(xx.shape)
            
            if i == 14:
                ax = plt.subplot(121)
            else:
                ax = plt.subplot(122)
#            image = plt.imshow(Z1, interpolation='nearest',
#                               extent=(xx.min(), xx.max(), yy.min(), yy.max()),
#                               aspect='auto', origin='lower', cmap=plt.cm.PuOr_r)
#            plt.colorbar(image)
            plt.contour(xx, yy, Z1, levels=[0], linewidths=5, linetypes='--', c='g', alpha=0.5) # estimated decision boundary
            CS = plt.contour(xx, yy, Z2, levels=[.2], linewidths=2, linetypes=':', c='b', alpha=.7)
            plt.clabel(CS, inline=1, fontsize=30)
            image = plt.imshow(Z3<0, interpolation='nearest',
                               extent=(xx.min(), xx.max(), yy.min(), yy.max()),
                               aspect='auto', origin='lower', cmap=plt.get_cmap('gray'), alpha=.3) # ground truth domain
            queried = plt.scatter(D[:, 0], D[:, 1], s=100, c='k', alpha=.7)
            initial = plt.scatter(D0[:, 0], D0[:, 1], s=100, c='w', alpha=.7, linewidth=2)
#            ax.add_patch(
#                patches.Rectangle(
#                    tuple(bounds_new[0]),
#                    bounds_new[1,0]-bounds_new[0,0],
#                    bounds_new[1,1]-bounds_new[0,1],
#                    fill=False
#                )
#            )
#            plt.title(r'$\Phi(|\bar{f}|+\epsilon)$', fontsize=fontsize)
            plt.xticks(())
            plt.yticks(())
            
            centerpoint = plt.scatter(center[0], center[1], s=700, c='r', marker='+', linewidth=4)
            newpoint = plt.scatter(new[0,0], new[0,1], s=700, c='y', marker='*')
        
        # Update model and dataset
        l = get_label(new, landmark, threshold)
        dataset.update(ask_id, l) # update dataset
        D = np.vstack((D, new))
        L = np.append(L, l)
            
        if np.any(np.array(L[-5:]) == 1) and np.any(np.array(L[-10:]) == -1):
            center = D[np.array(L) == 1][-1] # the last positive sample
        else:
            center = center0
        
        i += 1
        bounds_old = bounds_new
    
    plt.legend([initial, queried, centerpoint, newpoint], 
               ["Initial labeled samples", "Queried samples", "Center", "New query"],
               scatterpoints=1,
               loc='upper right',
               ncol=2,
               fontsize=32,
               bbox_to_anchor=(1, -.01, 0, 0),
               borderaxespad=0.)
    plt.tight_layout()

    plt.show()
