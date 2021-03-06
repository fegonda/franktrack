from nose.tools import * 
import template
import numpy as np
from matplotlib import pylab

def create_region(x, y):
    a = np.arange(x*y)
    a.shape = (y, x)
    return a
    
def test_overlap():
    ae = assert_equal
    # template / tgt same size
    ae(template.overlap(5, 5, 0), (0, 5))
    ae(template.overlap(5, 5, 1), (1, 5))
    ae(template.overlap(5, 5, 4), (4, 5))
    ae(template.overlap(5, 5, 5), (0, 0))

    ae(template.overlap(5, 5, -3), (0, 2))

    # check for smaller template
    ae(template.overlap(10, 5, 0), (0, 5))
    ae(template.overlap(10, 5, 1), (1, 6))
    ae(template.overlap(10, 5, 5), (5, 10))
    ae(template.overlap(10, 5, 10), (0, 0))
    
    # check for larger template
    ae(template.overlap(5, 10, 0), (0, 5))
    ae(template.overlap(5, 10, 1), (1, 5))
    ae(template.overlap(5, 10, 5), (0, 0))
    ae(template.overlap(5, 10, -5), (0, 5))
    
def test_template_select():
    # simple initial checks
    ae = assert_equal
    r1 = create_region(10, 5)
    t1 = create_region(3, 3)

    r1_a, t1_a = template.template_select(r1, t1, 0, 0)
    ae(r1_a.shape, (3, 3))
    ae(t1_a.shape, (3, 3))

    ae(r1_a[0, 0], 0)
    ae(r1_a[2, 2], 22)

    ae(t1_a[0, 0], 0)
    ae(t1_a[2, 2], 8)


    # simple offset
    r1 = create_region(10, 5)
    t1 = create_region(3, 3)
    r1_a, t1_a = template.template_select(r1, t1, 1, 2)
    ae(r1_a.shape, (3, 3))
    ae(t1_a.shape, (3, 3))

    ae(r1_a[0, 0], 21)
    ae(r1_a[2, 2], 43)

    ae(t1_a[0, 0], 0)
    ae(t1_a[2, 2], 8)

    # lower-right corner, almost
    r1 = create_region(10, 5)
    t1 = create_region(3, 3)
    r1_a, t1_a = template.template_select(r1, t1, 9, 3)
    ae(r1_a.shape, (2, 1))
    ae(t1_a.shape, (2, 1))

    ae(r1_a[0, 0], 39)
    ae(r1_a[1, 0], 49)

    ae(t1_a[0, 0], 0)
    ae(t1_a[1, 0], 3)

    # negative x-y spots
    r1 = create_region(10, 5)
    t1 = create_region(3, 4)
    r1_a, t1_a = template.template_select(r1, t1, -2, -1)
    ae(r1_a.shape, (3, 1))
    ae(t1_a.shape, (3, 1))

    ae(r1_a[0, 0], 0)
    ae(r1_a[2, 0], 20)

    ae(t1_a[0, 0], 5)
    ae(t1_a[2, 0], 11)


    # crazy values
    r1 = create_region(320, 240)
    t1 = create_region(34, 34)
    r1_a, t1_a = template.template_select(r1, t1, -17., -17.)

def test_template_render():

    tr = template.TemplateRenderGaussian()
    tr.set_params(14, 7, 4)

    i1 = tr.render(np.pi/2, np.pi/2)
    print type(i1), i1.shape
    
    pylab.subplot(1, 2, 1)
    pylab.imshow(i1, interpolation='nearest')

    pylab.colorbar()

    pylab.subplot(1, 2, 2)
    pylab.imshow(i1.mask.astype(float), interpolation='nearest')
    pylab.colorbar()
    #pylab.show()

def test_point_cloud_count():
    front_xy = (20.0, 40.)
    front_r = 5.
    back_xy = (40., 47.)
    back_r = 7.
    
    
    pcc = template.PointCloudCount(front_xy, front_r, 
                                 back_xy, back_r)
    
    points = []
    for x in range(200):
        for y in range(200):
            points.append((float(x)/2., float(y)/2.))

    points = np.array(points)
    
    fpi, bpi, bi = pcc.get_points(points)

    pylab.figure()
    pylab.scatter(points[fpi][:, 0], 
                   points[fpi][:, 1], c='g', linewidth=0)
    pylab.scatter(points[bpi][:, 0], 
                   points[bpi][:, 1], c='r', linewidth=0)
    pylab.scatter(points[bi][:, 0], 
                   points[bi][:, 1], c='b', linewidth=0)
    pylab.show()
