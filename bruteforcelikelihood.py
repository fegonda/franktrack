"""
Code to brute-force compare the likelihood model
"""

import numpy as np
import scipy.stats
import scipy.ndimage
import cPickle as pickle
import likelihood
import util2 as util
import model
import time
from matplotlib import pylab
import cloud
import plotparticles
import os
import organizedata
import videotools
import glob
import measure
import template


from ruffus import * 
import pf

PIX_THRESHOLD = 0
FL_DATA = "data/fl"

X_GRID_NUM = 150
Y_GRID_NUM = 150
PHI_GRID_NUM = 32
THETA_GRID_NUM =  6

USE_CLOUD = True
#cloud.start_simulator()

LIKELIHOOD_SETTING = [{'similarity' : 'dist',
                       'sim_params' : {'power' : 1}}, 
                      {'similarity' : 'normcc', 
                       'sim_params' : {'scalar': 10}}]

def params():
    EPOCHS = [#'bukowski_04.W1', 'bukowski_04.W2', 
              #'bukowski_03.W1', 
              'bukowski_03.W2', 
              #'bukowski_04.C', 'bukowski_03.C', 
              #'bukowski_03.linear', 'bukowski_04.linear'
              ]

    #'bukowski_04.C', 'bukowski_04.linear']
    FRAMES = np.arange(10)
    
    for epoch in EPOCHS:
        for frame in FRAMES:
            for likelihood_i in range(len(LIKELIHOOD_SETTING)):
                infiles = [os.path.join(FL_DATA, epoch), 
                          os.path.join(FL_DATA, epoch, 'config.pickle'), 
                          os.path.join(FL_DATA, epoch, 'framehist.npz'), 
                          ]
                basename = '%s.likelihoodscores.%02d.%05d.%d' % (epoch, likelihood_i, frame, PIX_THRESHOLD)
                outfiles = [basename + ".wait.pickle", 
                            basename + ".wait.npz"]

                yield (infiles, outfiles, epoch, frame, likelihood_i)
           

@files(params)
def score_frame_queue((dataset_dir, dataset_config_filename, 
            frame_hist_filename), (outfile_wait, 
                                   outfile_npz), dataset_name, frame, likelihood_i):

    np.random.seed(0)
    
    dataset_dir = os.path.join(FL_DATA, dataset_name)

    cf = pickle.load(open(dataset_config_filename))
    led_params = pickle.load(open(os.path.join(dataset_dir, "led.params.pickle")))

    EO = measure.led_params_to_EO(cf, led_params)

    x_range = np.linspace(0, cf['field_dim_m'][1], X_GRID_NUM)
    y_range = np.linspace(0, cf['field_dim_m'][0], Y_GRID_NUM)
    phi_range = np.linspace(0, 2*np.pi, PHI_GRID_NUM)
    degrees_from_vertical = 30
    radian_range = degrees_from_vertical/180. * np.pi
    theta_range = np.linspace(np.pi/2.-radian_range, 
                              np.pi/2. + radian_range, THETA_GRID_NUM)

    sv = create_state_vect(y_range, x_range, phi_range, theta_range)

    # now the input args
    chunk_size = 80000
    chunks = int(np.ceil(len(sv) / float(chunk_size)))

    args = []
    for i in range(chunks):
        args += [  (i*chunk_size, (i+1)*chunk_size)]

    CN = chunks
    results = []
    if USE_CLOUD: 
        print "MAPPING TO THE CLOUD" 
        jids = cloud.map(picloud_score_frame, [dataset_name]*CN,
                         [x_range]*CN, [y_range]*CN, 
                         [phi_range]*CN, [theta_range]*CN, 
                         args, [frame]*CN,  [EO]*CN, [likelihood_i]*CN,
                         _type='f2', _vol="my-vol", _env="base/precise")
    else:
        jids = map(picloud_score_frame, [dataset_name]*CN,
                   [x_range]*CN, [y_range]*CN, 
                   [phi_range]*CN, [theta_range]*CN, 
                   args, [frame]*CN,  [EO]*CN, [likelihood_i]*CN)
        

    np.savez_compressed(outfile_npz, 
                        x_range = x_range, y_range=y_range, 
                        phi_range = phi_range, theta_range = theta_range)
    pickle.dump({'frame' : frame, 
                 'dataset_name' : dataset_name, 
                 'dataset_dir' : dataset_dir, 
                 'jids' : jids}, open(outfile_wait, 'w'))


@transform(score_frame_queue, regex(r"(.+).wait.(.+)$"), [r"\1.pickle", r"\1.npz"])
def score_frame_wait((infile_wait, infile_npz), (outfile_pickle, outfile_npz)):
    dnpz = np.load(infile_npz)
    p = pickle.load(open(infile_wait))
    
    jids = p['jids']

    if USE_CLOUD:
        results = cloud.result(jids)
    else:
        results = [x for x in jids] 
    scores = np.concatenate(results)
    np.savez_compressed(outfile_npz, scores=scores, **dnpz)
    pickle.dump(p, open(outfile_pickle, 'w'))


@transform(score_frame_wait, suffix(".pickle"), [".png", ".hist.png"])
def plot_likelihood((infile_pickle, infile_npz),
                    (outfile, outfile_hist)):
    data = np.load(infile_npz)
    data_p = pickle.load(open(infile_pickle))
    scores = data['scores']

    sv = create_state_vect(data['y_range'], data['x_range'], 
                           data['phi_range'], data['theta_range'])

    scores = scores[:len(sv)]

    pylab.figure()
    scores_flat = np.array(scores.flat)
    pylab.hist(scores_flat[np.isfinite(scores_flat)], bins=255)
    pylab.savefig(outfile_hist, dpi=300)

    scores[np.isinf(scores)] = -1e20

    TOP_R, TOP_C = 3, 4
    TOP_N = TOP_R * TOP_C

    score_idx_sorted = np.argsort(scores)[::-1]
    
    #get the frame
    frames = organizedata.get_frames(data_p['dataset_dir'], 
                                     np.array([data_p['frame']]))

    # config file
    cf = pickle.load(open(os.path.join(data_p['dataset_dir'], 
                                       'config.pickle')))
    env = util.Environmentz(cf['field_dim_m'], 
                            cf['frame_dim_pix'])

    img = frames[0]
    f = pylab.figure()
    for r in range(TOP_N):
        s_i = score_idx_sorted[r]
        score = scores[s_i]
        ax =f.add_subplot(TOP_R, TOP_C, r+1)
        ax.imshow(img, interpolation='nearest', cmap=pylab.cm.gray)
        x_pix, y_pix = env.gc.real_to_image(sv[s_i]['x'], sv[s_i]['y'])
        ax.axhline(y_pix, linewidth=1, c='b', alpha=0.5)
        ax.axvline(x_pix, linewidth=1, c='b', alpha=0.5)
        ax.set_xticks([])
        ax.set_yticks([])
    f.subplots_adjust(bottom=0, left=.01, right=.99, top=.90, hspace=.1, wspace=.1)
    f.savefig(outfile, dpi=300)

@transform(score_frame_wait, suffix(".pickle"), [".zoom.png"])
def plot_likelihood_zoom((infile_pickle, infile_npz),
                         (zoom_outfile, )):
    """
    zoom in on the region of interest
    plot front and back diodes
    """
    data = np.load(infile_npz)
    data_p = pickle.load(open(infile_pickle))
    scores = data['scores']

    sv = create_state_vect(data['y_range'], data['x_range'], 
                           data['phi_range'], data['theta_range'])

    scores = scores[:len(sv)]

    TOP_R, TOP_C = 3, 4
    TOP_N = TOP_R * TOP_C

    score_idx_sorted = np.argsort(scores)[::-1]
    
    #get the frame
    frames = organizedata.get_frames(data_p['dataset_dir'], 
                                     np.array([data_p['frame']]))

    # config file
    cf = pickle.load(open(os.path.join(data_p['dataset_dir'], 
                                       'config.pickle')))
    env = util.Environmentz(cf['field_dim_m'], 
                            cf['frame_dim_pix'])
    tp = template.TemplateRenderCircleBorder()
    led_params = pickle.load(open(os.path.join(data_p['dataset_dir'], 
                                               "led.params.pickle")))

    EO_PARAMS = measure.led_params_to_EO(cf, led_params)

    tp.set_params(*EO_PARAMS)

    img = frames[0]
    img_thold = img.copy()
    img_thold[img < PIX_THRESHOLD] = 0
    f = pylab.figure(figsize=(12, 8))
    X_MARGIN = 30
    Y_MARGIN = 20
    for row in range(TOP_R):
        for col in range(TOP_C):
            r = row * TOP_C + col
            s_i = score_idx_sorted[r]
            score = scores[s_i]
            ax = pylab.subplot2grid((TOP_R *2, TOP_C*2), (row*2, col*2))
            ax.imshow(img, interpolation='nearest', cmap=pylab.cm.gray)
            ax_thold = pylab.subplot2grid((TOP_R*2, TOP_C*2), 
                                      (row*2+1, col*2))
            ax_thold.imshow(img_thold, interpolation='nearest', 
                            cmap=pylab.cm.gray, 
                            vmin=0, vmax=255)
            x = sv[s_i]['x']
            y = sv[s_i]['y']
            phi = sv[s_i]['phi']
            theta = sv[s_i]['theta']
            x_pix, y_pix = env.gc.real_to_image(x, y)

            # render the fake image
            ax_generated = pylab.subplot2grid((TOP_R*2, TOP_C*2), 
                                      (row*2+1, col*2 + 1))
            rendered_img = tp.render(phi, theta)
            ax_generated.imshow(rendered_img*255, interpolation='nearest', 
                                cmap=pylab.cm.gray, 
                                vmin = 0, vmax=255)
            # now compute position of diodes
            front_pos, back_pos = util.compute_pos(tp.length, x_pix, y_pix, 
                                                   phi, theta)

            cir = pylab.Circle(front_pos, radius=EO_PARAMS[1],  ec='g', fill=False,
                               linewidth=2)
            ax.add_patch(cir)
            cir = pylab.Circle(back_pos, radius=EO_PARAMS[2],  ec='r', fill=False, 
                               linewidth=2)
            ax.add_patch(cir)
            ax.set_title("%2.2f, %2.2f, %1.1f, %1.1f, %4.2f" % (x, y, phi, theta, score), size="xx-small")
            for a in [ax, ax_thold]:
                a.set_xticks([])
                a.set_yticks([])
                a.set_xlim(x_pix - X_MARGIN, x_pix+X_MARGIN)
                a.set_ylim(y_pix - Y_MARGIN, y_pix+Y_MARGIN)
    f.subplots_adjust(bottom=0, left=.01, right=.99, top=.90, hspace=.2, wspace=.1)
    f.savefig(zoom_outfile, dpi=300)



def create_state_vect(y_range, x_range, phi_range, theta_range):
    N = len(y_range) * len(x_range) * len(phi_range) * len(theta_range)

    state = np.zeros(N, dtype=util.DTYPE_STATE)
    
    i = 0
    for yi, y in enumerate(y_range):
        for xi, x in enumerate(x_range):
            for phii, phi in enumerate(phi_range):
                for thetai, theta in enumerate(theta_range):
                    state['x'][i] = x
                    state['y'][i] = y
                    state['phi'][i] = phi
                    state['theta'][i] = theta
                    i += 1
    return state

def picloud_score_frame(dataset_name, x_range, y_range, phi_range, theta_range,
                        state_idx, frame, EO_PARAMS, likelihood_i):
    """
    pi-cloud runner, every instance builds up full state, but
    we only evaluate the states in [state_idx_to_eval[0], state_idx_to_eval[1])
    and return scores
    """
    print "DATSET_NAME=", dataset_name
    dataset_dir = os.path.join(FL_DATA, dataset_name)
    dataset_config_filename = os.path.join(dataset_dir, "config.pickle")
    dataset_region_filename = os.path.join(dataset_dir, "region.pickle")
    frame_hist_filename = os.path.join(dataset_dir, "framehist.npz")
    
    np.random.seed(0)
    
    cf = pickle.load(open(dataset_config_filename))
    region = pickle.load(open(dataset_region_filename))

    framehist = np.load(frame_hist_filename)
    
    env = util.Environmentz(cf['field_dim_m'], 
                            cf['frame_dim_pix'])

    tp = template.TemplateRenderCircleBorder()
    
    tp.set_params(*EO_PARAMS)
    ls = LIKELIHOOD_SETTING[likelihood_i]
    
    le = likelihood.LikelihoodEvaluator2(env, tp, similarity=ls['similarity'], 
                                         sim_params = ls['sim_params'])

    frames = organizedata.get_frames(dataset_dir, np.array([frame]))
    frame = frames[0]
    frame[frame < PIX_THRESHOLD] = 0
    # create the state vector

    state = create_state_vect(y_range, x_range, phi_range, theta_range)
    
    SCORE_N = state_idx[1] - state_idx[0]
    scores = np.zeros(SCORE_N, dtype=np.float32)
    for i, state_i in enumerate(state[state_idx[0]:state_idx[1]]):
        x = state_i['x']
        y = state_i['y']
        if region['x_pos_min'] <= x <= region['x_pos_max'] and \
                region['y_pos_min'] <= y <= region['y_pos_max']:
            score = le.score_state(state_i, frame)
            scores[i] = score
        else:
            scores[i] = -1e100
    return scores

if __name__ == "__main__":
    pipeline_run([score_frame_wait, plot_likelihood, 
                  plot_likelihood_zoom], multiprocess=6)
