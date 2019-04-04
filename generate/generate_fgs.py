#!/usr/bin/env python
"""Script to generate FGS SIAF content and files using pysiaf and flight-like SIAF reference files.


Authors
-------

    Johannes Sahlmann

References
----------

    This code was partially adapted from Colin Cox' FGS2017.py, and
    FGS2017.py

    Created by Colin Cox on 2016-11-23.
    Fit using data from Julia Zhou's worksheeet

    For a detailed description of the MIRI SIAF, the underlying reference files, and the
    transformations,
    see Proffitt et al., 2017: The Pre-Flight SI Aperture File, Part 4: NIRSpec
    (JWST-STScI-005921).


"""


from collections import OrderedDict
import os
import time

import numpy as np
from astropy.io import ascii
from astropy.table import Table, vstack, Column
from astropy.time import Time
import pylab as pl

import pysiaf
from pysiaf.utils import polynomial, tools, compare
from pysiaf.constants import JWST_SOURCE_DATA_ROOT, JWST_TEMPORARY_DATA_ROOT
# from pysiaf.aperture import DISTORTION_ATTRIBUTES
# # from pysiaf.certify import compare
from pysiaf import iando
#
import generate_reference_files
#
import importlib
#
importlib.reload(pysiaf.tools)
# importlib.reload(pysiaf.aperture)
# # importlib.reload(pysiaf.aperture)
# importlib.reload(pysiaf.certify.compare)
# importlib.reload(pysiaf.iando.read)
importlib.reload(generate_reference_files)
# from pysiaf.certify import compare
# from pysiaf import iando
# from pysiaf import aperture

username = os.getlogin()
timestamp = Time.now()


#############################
instrument = 'FGS'
test_dir = os.path.join(JWST_TEMPORARY_DATA_ROOT, instrument, 'generate_test')

# regenerate SIAF reference files if needed

if 0:
    generate_reference_files.generate_initial_siaf_aperture_definitions(instrument)
    1/0
if 0:
    generate_reference_files.generate_siaf_detector_layout()

    generate_reference_files.generate_siaf_detector_reference_file(instrument)
    generate_reference_files.generate_siaf_ddc_mapping_reference_file(instrument)

# DDC name mapping
ddc_apername_mapping = iando.read.read_siaf_ddc_mapping_reference_file(instrument)

# NIRSpec detected parameters, e.g. XDetSize
siaf_detector_parameters = iando.read.read_siaf_detector_reference_file(instrument)

# Fundamental aperture definitions: names, types, reference positions, dependencies
siaf_aperture_definitions = iando.read.read_siaf_aperture_definitions(instrument)

# definition of the master apertures, the 16 SCAs
detector_layout = iando.read.read_siaf_detector_layout()
master_aperture_names = detector_layout['AperName'].data

# directory containing reference files delivered by IDT
source_data_dir = os.path.join(JWST_SOURCE_DATA_ROOT, instrument)
print ('Loading reference files from directory: {}'.format(source_data_dir))


def checkinv(A, B, C, D, order, center=False):
    '''Check that forward and inverse transformations are consistent'''
    points = 10
    rx = np.random.random(points)
    x = 2048* (rx)
    ry = np.random.random(points)
    y = 2048 * (ry)
    if center:
        x = x - 1024.0
        y = y - 1024.0
    u = polynomial.poly(A, x, y, order)
    v = polynomial.poly(B, x, y, order)
    x2 = polynomial.poly(C, u, v, order)
    y2 = polynomial.poly(D, u, v, order)
    print ('\nInverse Check')
    for p in range(points):
        print (8 * '%15.6f' % (x[p], y[p], u[p], v[p], x2[p], y2[p], x2[p] - x[p], y2[p] - y[p]))
    dx = x2 - x
    dy = y2 - y
    r = np.hypot(dx, dy)
    rms = np.sqrt((r ** 2).sum() / points)

    print('   Mean dx     Mean dy     RMSx         RMSy        RMS')
    #     1.497e-04   1.107e-04   1.274e-03   1.771e-03   2.028e-03

    print(5 * '%12.3e' % (dx.mean(), dy.mean(), dx.std(), dy.std(), rms))
    if rms > 0.01:
        print('Poor Inverse result')
    return


def fitstat(C, u, x, y, order):
    """Statistics of fit"""
    du = u - polynomial.poly(C, x, y, order)  # deltas of fit
    chisq = (du ** 2).sum()
    dof = len(u) - (order + 1) * (order + 2) // 2
    std = du.std()
    # print       4  4210  7.081e-02  1.682e-05  4.094e-03
    print ('   Order DOF  Chi-sq     Ch/DOF         STD\n %5d %5d %10.2e %10.2e %10.2e' % (order,
                                                                                           dof,
                                                                                           chisq,
                                                                                           chisq / dof,
                                                                                           std))
    return du


def addcoeffs(apline, CF, order):
    # add coeficients to apline
    k = 0
    for i in range(order + 1):
        for j in range(i + 1):
            apline += ',%22.15e' % CF[k]
            k += 1
    return apline

def generate_siaf_pre_flight_reference_files_fgs(use_cv3=False):
# def fit(order):
    order = 4

    if use_cv3:
        print ('\n\n\n*********************** FIT *************************************')
        print (time.ctime())  # Show when task was run
        print ('Fit of order', order)
        fgs = ascii.read(os.path.join(source_data_dir, 'FGS_RawCV3Data.csv'))
        x = fgs['X']
        y = fgs['Y']
        ix1 = fgs['V2F1']
        iy1 = fgs['V3F1']
        ix2 = fgs['V2F2']
        iy2 = fgs['V3F2']

        # Forward polynomials for FDGS1 and FGS2
        A1 = polynomial.polyfit(ix1, x, y, order)
        B1 = polynomial.polyfit(iy1, x, y, order)
        A2 = polynomial.polyfit(ix2, x, y, order)
        B2 = polynomial.polyfit(iy2, x, y, order)
    else:

        # copied from Cox' makeSIAF.py to reproduce PRDOPSSOC-H-015
        # February 2015 FGS delivery
        # Initialize the parameters
        xOffset = 1023.5,
        yOffset = 1023.5,
        scale = 0.06738281367

        A1 = np.array([-2.33369320E+01, 9.98690490E-01, 1.05024970E-02, 2.69889020E-06, 6.74362640E-06,
                           9.91415010E-07, 1.21090320E-09, -2.84802930E-11, 1.27892930E-09, -1.91322470E-11,
                           5.34567520E-14, 9.29791010E-14, 8.27060020E-14, 9.70576590E-14, 1.94203870E-14])

        B1 = np.array([-2.70337440E+01, -2.54596080E-03, 1.01166810E+00, 2.46371870E-06, 2.08880620E-06,
                           9.32489680E-06, -4.11885660E-11, 1.26383770E-09, -7.60173360E-11, 1.36525900E-09,
                           2.70499280E-14, 5.70198270E-14, 1.43943080E-13, 7.02321790E-14, 1.21579450E-13])

        C1 = np.array(
            [2.31013520E+01, 1.00091800E+00, -1.06389620E-02, -2.65680980E-06, -6.51704610E-06,
             -7.45631440E-07, -1.29600400E-09, -4.27453220E-12, -1.27808870E-09, 5.01165140E-12,
             2.72622090E-15, 5.42715750E-15, 3.46979980E-15, 2.49124350E-15, 1.22848570E-15])

        D1 = np.array([2.67853100E+01, 2.26545910E-03, 9.87816850E-01, -2.35598140E-06, -1.91455620E-06,
                           -8.92779540E-06, -3.24201520E-11, -1.30056630E-09, -1.73730700E-11,
                           -1.27341590E-09, 1.84205730E-15, 3.13647160E-15, -2.99705840E-16, 1.98589690E-15,
                           -1.26523200E-15])

        A2 = np.array(
            [-3.28410900E+01, 1.03455010E+00, 2.11920160E-02, -9.08746430E-06, -1.43516480E-05,
             -3.93814140E-06, 1.60956450E-09, 5.82814640E-10, 2.02870570E-09, 2.08582470E-10,
             -2.79748590E-14, -8.11622820E-14, -4.76943000E-14, -9.01937740E-14, -8.76203780E-15])

        B2 = np.array(
            [-7.76806220E+01, 2.92234710E-02, 1.07790000E+00, -6.31144890E-06, -7.87266390E-06,
             -2.14170580E-05, 2.13293560E-10, 2.03376270E-09, 6.74607790E-10, 2.41463060E-09,
             -2.30267730E-14, -3.63681270E-14, -1.35117660E-13, -4.22207660E-14, -1.16201020E-13])

        C2 = np.array([3.03390890E+01, 9.68539030E-01, -1.82288450E-02, 7.72758330E-06, 1.17536430E-05,
                           2.71516870E-06, -1.28167820E-09, -6.34376120E-12, -1.24563160E-09,
                           -9.26192040E-12, 8.14604260E-16, -5.93798790E-16, -2.69247540E-15,
                           -4.05196100E-15, 2.14529600E-15])

        D2 = np.array([7.13783150E+01, -2.55191710E-02, 9.30941560E-01, 5.01322910E-06, 5.10548510E-06,
                           1.68083960E-05, 9.41565630E-12, -1.29749490E-09, -1.89194230E-11,
                           -1.29425530E-09, -2.81501600E-15, -1.73025000E-15, 2.57732600E-15,
                           1.75268080E-15, 2.95238320E-15])

    print ('A1')
    polynomial.print_triangle(A1)
    print ('B1')
    polynomial.print_triangle(B1)
    print ('A2')
    polynomial.print_triangle(A2)
    print ('B2')
    polynomial.print_triangle(B2)

    fgs = open(os.path.join(test_dir, 'FGScoeffs.csv'), 'w')
    if use_cv3:
        print ('\nA1')
        dax1 = fitstat(A1, ix1, x, y, order)
        print ('B1')
        day1 = fitstat(B1, iy1, x, y, order)
        print ('A2')
        dax2 = fitstat(A2, ix2, x, y, order)
        print ('B2')
        day2 = fitstat(B2, iy2, x, y, order)

        # Inverse polynomials for FGS1 and FGS2
        C1 = polynomial.polyfit(x, ix1, iy1, order)
        D1 = polynomial.polyfit(y, ix1, iy1, order)
        C2 = polynomial.polyfit(x, ix2, iy2, order)
        D2 = polynomial.polyfit(y, ix2, iy2, order)

        print ('C2')
        polynomial.print_triangle(C2)
        print ('D2')
        polynomial.print_triangle(D2)

    # if use_cv3:
        # Fit statistics
        print ('\nC1')
        dpx1 = fitstat(C1, x, ix1, iy1, order)
        print ('D1')
        dpy1 = fitstat(D1, y, ix1, iy1, order)
        print ('C2')
        dpx2 = fitstat(C2, x, ix2, iy2, order)
        print ('D2')
        dpy2 = fitstat(D2, y, ix2, iy2, order)

        print ('\nCenter')
        if use_cv3:
            V2Ref = polynomial.poly(A1, 1023.5, 1023.5, order)
            V3Ref = polynomial.poly(B1, 1023.5, 1023.5, order)
        else:
            V2Ref = 207.1900
            V3Ref = -697.5000
        print (V2Ref, V3Ref)
        print('\nCalculated Corners')
        cx = np.array([-0.5, 2047.5, 2047.5, -0.5, -0.5])
        cy = np.array([-0.5, -0.5, 2047.5, 2047.5, -0.5])
        xcorner = polynomial.poly(A1, cx, cy, order)
        ycorner = polynomial.poly(B1, cx, cy, order)
        for c in range(4):
            print ('%10.4f %10.4f' % (xcorner[c], ycorner[c]))

        betax1 = np.arctan2(A1[1], B1[1])
        betay1 = np.arctan2(A1[2], B1[2])
        print ('\nBefore Shifting')
        print (
        'Angles1 %10.4f %10.4f %10.4f' % (np.rad2deg(betax1), np.rad2deg(betay1), np.rad2deg(betay1 - betax1)))

        A1S = polynomial.shift_coefficients(A1, 1023.5, 1023.5, order)
        B1S = polynomial.shift_coefficients(B1, 1023.5, 1023.5, order)
        print ('Shifted')
        print('A1S')
        polynomial.print_triangle(A1S)
        print('B1S')
        polynomial.print_triangle(B1S)
        parity = 1  # for OSS
        xscale = np.hypot(A1S[1], B1S[1])
        yscale = np.hypot(A1S[2], B1S[2])
        xangle = np.rad2deg(np.arctan2(parity * A1S[1], B1S[1]))
        yangle = np.rad2deg(np.arctan2(parity * A1S[2], B1S[2]))

        print ('\nLinear matrix\n %10.6f %10.6f \n %10.6f %10.6f' % (A1S[1], A1S[2], B1S[1], B1S[2]))
        print ('Scales %12.6f %12.6f' % (xscale, yscale))
        print ('Angles %12.6f %12.6f' % (xangle, yangle))

        print ('\nRecalculated Corners')
        cxs = np.array([-1024.0, 1024.0, 1024.0, -1024.0, -1024.0])
        cys = np.array([-1024.0, -1024.0, 1024.0, 1024.0, -1024.0])
        xcorner = polynomial.poly(A1S, cxs, cys, order)
        ycorner = polynomial.poly(B1S, cxs, cys, order)
        for c in range(4):
            print ('%10.4f %10.4f' % (xcorner[c], ycorner[c]))

        V2Ref1 = A1S[0]
        V3Ref1 = B1S[0]
        A1S[0] = 0.0
        B1S[0] = 0.0

        pl.figure(1)
        pl.clf()
        pl.plot(xcorner, ycorner, '-')
        pl.plot(xcorner[0], ycorner[0], 'bs')
        pl.plot(V2Ref, V3Ref, 'b+')
        pl.text(V2Ref, V3Ref, 'FGS1')
        pl.text(xcorner[1], ycorner[1], 'X')
        pl.text(xcorner[3], ycorner[3], 'Y')
        pl.grid(True)
        pl.axis('equal')
        pl.show()

        print ('\nAfter Shifting')
        print ('Angles %10.4f %10.4f' % (xangle, yangle))
        if abs(yangle) > 90.0:
            V3angle = yangle - np.sign(yangle) * 180.0
            print ('Modified yangle %10.4f' % V3angle)
        else:
            V3angle = yangle

        # Rotate polynomial to create Ideal coefficients
        A1SR = A1S * np.cos(np.deg2rad(V3angle)) - B1S * np.sin(np.deg2rad(V3angle))
        B1SR = A1S * np.sin(np.deg2rad(V3angle)) + B1S * np.cos(np.deg2rad(V3angle))
        print (A1SR[2])
        if abs(A1SR[2]) < 1.0e-10:
            A1SR[2] = 0.0
            print ('A1SR[2] set to zero')
        else:
            print('-----------------------------------A1SR[2] non-zero')

        print ('\nRotated coefficiients\nA1SR')
        polynomial.print_triangle(A1SR)
        print ('B1SR')
        polynomial.print_triangle(B1SR)

        # Prepare csv file with output parameters

        topline = 'Aperture,   V3IdlYangle, xangle,  yangle'

        for i in range(order + 1):
            for j in range(i + 1):
                topline += ', A' + str(i) + str(j)
        for i in range(order + 1):
            for j in range(i + 1):
                topline += ', B' + str(i) + str(j)

        for i in range(order + 1):
            for j in range(i + 1):
                topline += ', C' + str(i) + str(j)

        for i in range(order + 1):
            for j in range(i + 1):
                topline += ', D' + str(i) + str(j)
        topline = topline + '\n'
        fgs.write(topline)


        # Inverse
        print ('\nNow do inverses')
        print ('C1')
        polynomial.print_triangle(C1)
        print ('D1')
        polynomial.print_triangle(D1)

        C1S = polynomial.shift_coefficients(C1, V2Ref1, V3Ref1, order)
        D1S = polynomial.shift_coefficients(D1, V2Ref1, V3Ref1, order)
        C1S[0] = 0.0
        D1S[0] = 0.0
        print ('\nC1S')
        polynomial.print_triangle(C1S)
        print('D1S')
        polynomial.print_triangle(D1S)

        print ('Check 1S transforms')
        checkinv(A1S, B1S, C1S, D1S, order, center=True)

        print ('Rotate by ', V3angle)
        C1SR = polynomial.prepend_rotation_to_polynomial(C1S, V3angle, order)
        D1SR = polynomial.prepend_rotation_to_polynomial(D1S, V3angle, order)
        print ('\nC1SR')
        polynomial.print_triangle(C1SR)
        print('D1SR')
        polynomial.print_triangle(D1SR)
        print ('Check 1SR transformations')
        checkinv(A1SR, B1SR, C1SR, D1SR, order, center=True)
    else:
        A = A1
        B = B1
        C = C1
        D = D1


        V2Ref = 207.1900
        V3Ref = -697.5000
        xiRef = polynomial.poly(A, 1023.5, 1023.5)
        yiRef = polynomial.poly(B, 1023.5, 1023.5)
        print('Ideal center %8.3f %8.3f' % (xiRef, yiRef))
        print('Inverse check of incoming poynomials')
        checkinv(A, B, C, D, order)
        AS = polynomial.shift_coefficients(A, 1023.5, 1023.5)
        AS[0] = 0.0
        BS = polynomial.shift_coefficients(B, 1023.5, 1023.5)
        BS[0] = 0.0
        CS = polynomial.shift_coefficients(C, xiRef, yiRef)
        CS[0] = 0.0
        DS = polynomial.shift_coefficients(D, xiRef, yiRef)
        DS[0] = 0.0

        # print('\nAS')
        # triangle(AS)
        # print('BS')
        # triangle(BS)
        # print('Shifted')
        # checkinv(AS, BS, CS, DS, 4)

        # parity = 1  # for OSS
        # xangle = np.rad2deg(np.arctan2(parity * AS[1], BS[1]))
        # yangle = np.rad2deg(np.arctan2(parity * AS[2], BS[2]))
        # parity = 1  # for OSS



        xd = 300
        yd = 700
        u = polynomial.poly(AS, xd, yd)
        v = polynomial.poly(BS, xd, yd)
        print('Solution   %8.3f %8.3f' % (xd, yd))
        print('Raw values %8.3f %8.3f' % (u, v))
        xs = xd  # For OSS detector and science are identical
        ys = yd

        AF = AS
        BF = -BS

        # print('\nAF')
        # triangle(AF)
        # print('BF')
        # triangle(BF)

        xi = polynomial.poly(AF, xs, ys)
        yi = polynomial.poly(BF, xs, ys)
        print('Ideal values')
        print(' %8.3f %8.3f' % (xs, ys))
        print(' %8.3f %8.3f' % (xi, yi))

        CF = polynomial.flip_y(CS)
        DF = polynomial.flip_y(DS)

        # print('\nCS')
        # triangle(CS)
        # print('DS')
        # triangle(DS)
        # print('CF')
        # triangle(CF)
        # print('DF')
        # triangle(DF)

        xdr = polynomial.poly(CF, xi, yi)
        ydr = polynomial.poly(DF, xi, yi)
        print('Regained Detector  %8.3f %8.3f' % (xdr, ydr))

        betaX = np.arctan2(AF[1], BF[1])
        betaY = np.arctan2(AF[2], BF[2])
        xangle = np.rad2deg(betaX)
        yangle = np.rad2deg(betaY)
        if np.abs(betaY) > np.pi / 2:
            V3angle = betaY - np.copysign(np.pi, betaY)
        else:
            V3angle = betaY

        print('\nAngles')
        print('betaX   %10.4f' % np.degrees(betaX))
        print('betaY   %10.4f' % np.degrees(betaY))
        print('V3angle %10.4f' % np.degrees(V3angle))


        (AR, BR) = polynomial.add_rotation(AF, BF, -np.degrees(V3angle))
        # print('AR')
        # triangle(AR)
        # print('BR')
        # triangle(BR)

        xii = polynomial.poly(AR, xs, ys)
        yii = polynomial.poly(BR, xs, ys)
        print('Ideal Rotated  %8.3f %8.3f' % (xii, yii))
        (u, v) = polynomial.add_rotation(xii, yii, -betaY)
        print('Ideal again %8.3f %8.3f' % (u, v))

        # (CR,DR) = polynomial.add_rotation(CF,DF, -betaY)
        CR = polynomial.prepend_rotation_to_polynomial(CF, np.degrees(V3angle))
        DR = polynomial.prepend_rotation_to_polynomial(DF, np.degrees(V3angle))
        # print('\nCR')
        # triangle(CR)
        # print('DR')
        # triangle(DR)
        xs3 = polynomial.poly(CR, xii, yii)
        ys3 = polynomial.poly(DR, xii, yii)
        print('Regained rotated Science %8.3f %8.3f' % (xs3, ys3))
        print('Final coefficients before scaling')
        checkinv(AR, BR, CR, DR, order)
        print('Ideal pixel size', scale, ' arcsec')

        (AR, BR, CR, DR) = polynomial.rescale(AR, BR, CR, DR, scale)
        A1SR, B1SR, C1SR, D1SR = AR, BR, CR, DR
        # print('After Scaling')
        # print('AR')
        # triangle(AR, 4)
        # print('BR')
        # triangle(BR, 4)
        # print('CR')
        # triangle(CR, 4)
        # print('DR')
        # triangle(DR, 4)
        # checkinv(AR, BR, CR, DR, order)  # Add to csv file

        # hack!
        A1S, B1S, C1S, D1S = AS, BS, CS, DS
        cx = np.zeros(4)
        cy = np.zeros(4)
        cxs = np.zeros(4)
        cys = np.zeros(4)

    apline = 'FGS1_FULL_OSS,  %12.6f,  %12.6f,  %12.6f' % (V3angle, xangle, yangle)
    apline = addcoeffs(apline, A1SR, order)
    apline = addcoeffs(apline, B1SR, order)
    apline = addcoeffs(apline, C1SR, order)
    apline = addcoeffs(apline, D1SR, order)
    fgs1_oss = {'A': A1SR, 'B': B1SR, 'C': C1SR, 'D': D1SR}
    fgs1_oss['V2Ref'] = V2Ref
    fgs1_oss['V3Ref'] = V3Ref
    fgs1_oss['V3IdlYAngle'] = np.rad2deg(V3angle)
    fgs1_oss['V3SciXAngle'] = xangle
    fgs1_oss['V3SciYAngle'] = yangle
    apline += '\n'
    fgs.write(apline)

    print ('-------------------------FGS1 DMS-------------------------------')
    # Different axis directions.
    parity = -1
    A1S = -polynomial.flip_xy(A1S)
    B1S = polynomial.flip_xy(B1S)
    print ('\nA1S')
    polynomial.print_triangle(A1S)
    print ('B1S')
    polynomial.print_triangle(B1S)
    C1S = -polynomial.flip_x(C1S)
    D1S = -polynomial.flip_x(D1S)
    print('\nC1S')
    polynomial.print_triangle(C1S)
    print ('D1S')
    polynomial.print_triangle(D1S)
    checkinv(A1S, B1S, C1S, D1S, order, center=True)

    # Rotate polynomial to create Ideal coefficients
    print ('\nLinear matrix\n %10.6f %10.6f \n %10.6f %10.6f' % (A1S[1], A1S[2], B1S[1], B1S[2]))
    xangle = np.rad2deg(np.arctan2(parity * A1S[1], B1S[1]))
    yangle = np.rad2deg(np.arctan2(parity * A1S[2], B1S[2]))
    print ('Angles %10.4f %10.4f' % (xangle, yangle))
    if abs(yangle) > 90.0:
        V3angle = yangle - np.sign(yangle) * 180.0
        print ('Modified yangle %10.4f' % V3angle)
    else:
        V3angle = yangle

    # Rotate polynomial to create Ideal coefficients
    A1SR = A1S * np.cos(np.deg2rad(-V3angle)) - B1S * np.sin(np.deg2rad(-V3angle))
    B1SR = A1S * np.sin(np.deg2rad(-V3angle)) + B1S * np.cos(np.deg2rad(-V3angle))
    print (A1SR[2])
    if abs(A1SR[2]) < 1.0e-10:
        A1SR[2] = 0.0
        print ('A1SR[2] set to zero')
    else:
        print('----------------------------------A1SR[2] non-zero')
    print ('\nRotated coefficiients\nA1SR')
    polynomial.print_triangle(A1SR)
    print ('B1SR')
    polynomial.print_triangle(B1SR)
    C1SR = polynomial.prepend_rotation_to_polynomial(C1S, -V3angle, order)
    D1SR = polynomial.prepend_rotation_to_polynomial(D1S, -V3angle, order)
    print ('\nC1SR')
    polynomial.print_triangle(C1SR)
    print('D1SR')
    polynomial.print_triangle(D1SR)
    print ('Check 1SR transformations')
    checkinv(A1SR, B1SR, C1SR, D1SR, order, center=True)

    apline = 'FGS1_FULL,  %12.6f,  %12.6f,  %12.6f' % (V3angle, xangle, yangle)
    apline = addcoeffs(apline, A1SR, order)
    apline = addcoeffs(apline, B1SR, order)
    apline = addcoeffs(apline, C1SR, order)
    apline = addcoeffs(apline, D1SR, order)
    apline += '\n'
    fgs.write(apline)

    fgs1 = {'A': A1SR, 'B': B1SR, 'C': C1SR, 'D': D1SR}
    fgs1['V2Ref'] = V2Ref
    fgs1['V3Ref'] = V3Ref
    fgs1['V3IdlYAngle'] = V3angle
    fgs1['V3SciXAngle'] = xangle
    fgs1['V3SciYAngle'] = yangle


    print('\n\n')
    print(' -------------------FGS2-----------------------------------')
    print()
    print ('A2')
    polynomial.print_triangle(A2)
    print ('B2')
    polynomial.print_triangle(B2)

    print ('\nCenter')
    V2Ref = polynomial.poly(A2, 1023.5, 1023.5, order)
    V3Ref = polynomial.poly(B2, 1023.5, 1023.5, order)
    print (2 * '%12.4f' % (V2Ref, V3Ref))

    print('\nCalculated Corners')
    xcorner = polynomial.poly(A2, cx, cy, order)
    ycorner = polynomial.poly(B2, cx, cy, order)
    for c in range(4):
        print ('%10.4f %10.4f' % (xcorner[c], ycorner[c]))

    pl.figure(1)
    pl.plot(xcorner, ycorner, '-')
    pl.plot(xcorner[0], ycorner[0], 'gs')
    pl.plot(V2Ref, V3Ref, 'g+')
    pl.text(V2Ref, V3Ref, 'FGS2')
    pl.text(xcorner[1], ycorner[1], 'X')
    pl.text(xcorner[3], ycorner[3], 'Y')
    pl.xlabel('V2')
    pl.ylabel('V3')
    u = pl.axis()
    v = (u[1], u[0], u[2], u[3])  # Reverse x direction
    pl.axis(v)  # Show V2 increasing to the left

    parity = +1
    xangle = np.rad2deg(parity * np.arctan2(A2[1], B2[1]))
    yangle = np.rad2deg(parity * np.arctan2(A2[2], B2[2]))
    print ('Angles2 %12.4f %12.4f' % (xangle, yangle))

    A2S = polynomial.shift_coefficients(A2, 1023.5, 1023.5, order)
    B2S = polynomial.shift_coefficients(B2, 1023.5, 1023.5, order)
    print ('Shifted')
    print('A2S')
    polynomial.print_triangle(A2S)
    print('B2S')
    polynomial.print_triangle(B2S)
    xangle = np.rad2deg(parity * np.arctan2(A2S[1], B2S[1]))
    yangle = np.rad2deg(parity * np.arctan2(A2S[2], B2S[2]))

    print ('\nRecalculated Corners')
    xcorner = polynomial.poly(A2S, cxs, cys, order)
    ycorner = polynomial.poly(B2S, cxs, cys, order)
    for c in range(4):
        print ('%10.4f %10.4f' % (xcorner[c], ycorner[c]))

    print ('\nAfter Shifting')
    print ('\nLinear matrix\n %10.6f %10.6f \n %10.6f %10.6f' % (A2S[1], A2S[2], B2S[1], B2S[2]))
    xscale = np.hypot(A2S[1], B2S[1])
    yscale = np.hypot(A2S[2], B2S[2])
    print ('Scales %12.6f %12.6f' % (xscale, yscale))
    print ('Angles2 %12.4f %12.4f' % (xangle, yangle))
    if abs(yangle) > 90.0:
        V3angle = yangle - np.sign(yangle) * 180.0
        print ('Modified yangle ', V3angle)
    else:
        V3angle = yangle

    # Separate V2V3 ref
    V2Ref2 = A2S[0]
    V3Ref2 = B2S[0]
    A2S[0] = 0.0
    B2S[0] = 0.0

    # Rotate polynomial to create Ideal coefficients
    A2SR = A2S * np.cos(np.deg2rad(V3angle)) - B2S * np.sin(np.deg2rad(V3angle))
    B2SR = A2S * np.sin(np.deg2rad(V3angle)) + B2S * np.cos(np.deg2rad(V3angle))
    print (A2SR[2])
    if abs(A2SR[2]) < 1.0e-10:
        A2SR[2] = 0.0
        print ('A2SR[2] set to zero')
    else:
        print('------------------------------------A2SR[2] non-zero')

    print ('\nRotated coefficients\nA2SR')
    polynomial.print_triangle(A2SR)
    print ('B2R')
    polynomial.print_triangle(B2SR)

    # Inverse
    print ('\nNow do inverses')
    print ('C2')
    polynomial.print_triangle(C2)
    print ('D2')
    polynomial.print_triangle(D2)

    C2S = polynomial.shift_coefficients(C2, V2Ref2, V3Ref2, order)
    D2S = polynomial.shift_coefficients(D2, V2Ref2, V3Ref2, order)
    C2S[0] = 0.0
    D2S[0] = 0.0
    print ('\nC2S')
    polynomial.print_triangle(C2S)
    print('D2S')
    polynomial.print_triangle(D2S)

    print ('Check 2S transforms')
    checkinv(A2S, B2S, C2S, D2S, order, center=True)

    print ('Rotate by ', yangle)
    C2SR = polynomial.prepend_rotation_to_polynomial(C2S, V3angle, order)
    D2SR = polynomial.prepend_rotation_to_polynomial(D2S, V3angle, order)
    print ('\nC2SR')
    polynomial.print_triangle(C2SR)
    print('D2SR')
    polynomial.print_triangle(D2SR)
    print ('Check 2SR transformations')
    checkinv(A2SR, B2SR, C2SR, D2SR, order, center=True)

    apline = 'FGS2_FULL_OSS,  %12.6f,  %12.6f,  %12.6f' % (V3angle, xangle, yangle)
    apline = addcoeffs(apline, A2SR, order)
    apline = addcoeffs(apline, B2SR, order)
    apline = addcoeffs(apline, C2SR, order)
    apline = addcoeffs(apline, D2SR, order)
    apline += '\n'
    fgs.write(apline)

    fgs2_oss = {'A': A2SR, 'B': B2SR, 'C': C2SR, 'D': D2SR}
    fgs2_oss['V2Ref'] = V2Ref
    fgs2_oss['V3Ref'] = V3Ref
    fgs2_oss['V3IdlYAngle'] = V3angle
    fgs2_oss['V3SciXAngle'] = xangle
    fgs2_oss['V3SciYAngle'] = yangle

    print ('----------------------------------- FGS2 DMS --------------')
    parity = -1
    A2S = -polynomial.flip_x(A2S)
    B2S = polynomial.flip_x(B2S)
    print ('\nA2S')
    polynomial.print_triangle(A2S)
    print ('\B2S')
    polynomial.print_triangle(B2S)

    C2S = -polynomial.flip_x(C2S)
    D2S = polynomial.flip_x(D2S)
    print ('\nC2S')
    polynomial.print_triangle(C2S)
    print ('\D2S')
    polynomial.print_triangle(D2S)

    print ('\nLinear matrix\n %10.6f %10.6f \n %10.6f %10.6f' % (A2S[1], A2S[2], B2S[1], B2S[2]))


    xangle = np.rad2deg(np.arctan2(parity * A1S[1], B1S[1]))
    yangle = np.rad2deg(np.arctan2(parity * A2S[2], B2S[2]))
    print ('yangle', yangle)
    if abs(yangle) > 90.0:
        V3angle = yangle - np.sign(yangle) * 180.0
        print ('Modified yangle ', V3angle)
    else:
        V3angle = yangle

    A2SR = A2S * np.cos(np.deg2rad(-V3angle)) - B2S * np.sin(np.deg2rad(-V3angle))
    B2SR = A2S * np.sin(np.deg2rad(-V3angle)) + B2S * np.cos(np.deg2rad(-V3angle))
    print (A2SR[2])
    if abs(A2SR[2]) < 1.0e-10:
        A2SR[2] = 0.0
        print ('A2SR[2] set to zero')
    else:
        print('---------------------------------------A2SR[2] non-zero')

    print ('\nRotated coefficiients\nA2SR')
    polynomial.print_triangle(A2SR)
    print ('B2SR')
    polynomial.print_triangle(B2SR)
    C2SR = polynomial.prepend_rotation_to_polynomial(C2S, -V3angle, order)
    D2SR = polynomial.prepend_rotation_to_polynomial(D2S, -V3angle, order)
    print ('\nC2SR')
    polynomial.print_triangle(C2SR)
    print('D2SR')
    polynomial.print_triangle(D2SR)
    print ('Check 2SR transformations')
    checkinv(A2SR, B2SR, C2SR, D2SR, order, center=True)

    apline = 'FGS2_FULL,  %12.6f,  %12.6f,  %12.6f' % (V3angle, xangle, yangle)
    apline = addcoeffs(apline, A2SR, order)
    apline = addcoeffs(apline, B2SR, order)
    apline = addcoeffs(apline, C2SR, order)
    apline = addcoeffs(apline, D2SR, order)
    apline += '\n'
    fgs.write(apline)
    fgs2 = {'A': A2SR, 'B': B2SR, 'C': C2SR, 'D': D2SR}
    fgs2['V2Ref'] = V2Ref2
    fgs2['V3Ref'] = V3Ref2
    fgs2['V3IdlYAngle'] = V3angle
    fgs2['V3SciXAngle'] = xangle
    fgs2['V3SciYAngle'] = yangle

    fgs.close()  # Finish csv file


    # write SIAF reference files
    number_of_coefficients = len(A2SR)
    polynomial_degree = np.int((np.sqrt(8 * number_of_coefficients + 1) - 3) / 2)
    siaf_index = []
    exponent_x = []
    exponent_y = []
    for i in range(polynomial_degree + 1):
        for j in np.arange(i + 1):
            siaf_index.append('{:d}{:d}'.format(i, j))
            exponent_x.append(i - j)
            exponent_y.append(j)

    fgs_dict = {'fgs1': fgs1, 'fgs2': fgs2, 'fgs1_oss': fgs1_oss, 'fgs2_oss': fgs2_oss }





    siaf_alignment = Table()
    for fgs_tag in fgs_dict.keys():
        fgs_data = fgs_dict[fgs_tag]

        if fgs_tag == 'fgs1':
            aperture_name = 'FGS1_FULL'
        elif fgs_tag == 'fgs1_oss':
            aperture_name = 'FGS1_FULL_OSS'
        elif fgs_tag == 'fgs2':
            aperture_name = 'FGS2_FULL'
        elif fgs_tag == 'fgs2_oss':
            aperture_name = 'FGS2_FULL_OSS'
        A = fgs_data['A']
        B = fgs_data['B']
        C = fgs_data['C']
        D = fgs_data['D']

        distortion_reference_table = Table((siaf_index, exponent_x, exponent_y, A, B, C, D),
                                           names=(
                                               'siaf_index', 'exponent_x', 'exponent_y', 'Sci2IdlX',
                                               'Sci2IdlY', 'Idl2SciX', 'Idl2SciY'))
        distortion_reference_table.add_column(
            Column([aperture_name] * len(distortion_reference_table), name='AperName'), index=0)
        distortion_reference_file_name = os.path.join(JWST_SOURCE_DATA_ROOT, instrument,
                                                      '{}_siaf_distortion_{}.txt'.format(instrument.lower(),
                                                          aperture_name.lower()))
        distortion_reference_table.pprint()
        comments = []
        comments.append('FGS distortion reference file for SIAF\n')
        comments.append('Aperture: {}'.format(aperture_name))
        comments.append('Based on a fit to data provided in FGS_RawCV3Data.csv')
        comments.append('These parameters are stored in PRDOPSSOC-H-014.')
        comments.append('')
        comments.append('Generated {} {}'.format(timestamp.isot, timestamp.scale))
        comments.append('by {}'.format(username))
        comments.append('')
        distortion_reference_table.meta['comments'] = comments
        distortion_reference_table.write(distortion_reference_file_name, format='ascii.fixed_width',
                                         delimiter=',', delimiter_pad=' ', bookend=False, overwrite=True)

        # alignment reference file

        if len(siaf_alignment) == 0:
            siaf_alignment['AperName'] = ['{:>30}'.format(aperture_name)]
            siaf_alignment['V3IdlYAngle'] = [fgs_data['V3IdlYAngle']]
            siaf_alignment['V3SciXAngle'] = [fgs_data['V3SciXAngle']]
            siaf_alignment['V3SciYAngle'] = [fgs_data['V3SciYAngle']]
            siaf_alignment['V2Ref'] = [fgs_data['V2Ref']]
            siaf_alignment['V3Ref'] = [fgs_data['V3Ref']]
        else:
            siaf_alignment.add_row(
                ['{:>30}'.format(aperture_name), fgs_data['V3IdlYAngle'], fgs_data['V3SciXAngle'],
                 fgs_data['V3SciYAngle'], fgs_data['V2Ref'], fgs_data['V3Ref']])


    outfile = os.path.join(JWST_SOURCE_DATA_ROOT, instrument,
                       '{}_siaf_alignment.txt'.format(instrument.lower()))
    comments = []
    comments.append('{} alignment parameter reference file for SIAF'.format(instrument))
    comments.append('')
    comments.append('This file contains the focal plane alignment parameters calibrated during FGS-FGS alignment.')
    comments.append('')
    comments.append('Generated {} {}'.format(timestamp.isot, timestamp.scale))
    comments.append('by {}'.format(username))
    comments.append('')
    siaf_alignment.meta['comments'] = comments
    siaf_alignment.write(outfile, format='ascii.fixed_width', delimiter=',',
                                     delimiter_pad=' ', bookend=False, overwrite=True)

    return


generate_preflight_alignemnt_and_distortion_reference_files = False
if generate_preflight_alignemnt_and_distortion_reference_files:
    generate_reference_files.generate_siaf_pre_flight_reference_files_fgs()

siaf_alignment_parameters = iando.read.read_siaf_alignment_parameters(instrument)

aperture_dict = OrderedDict()
aperture_name_list = siaf_aperture_definitions['AperName'].tolist()

for AperName in aperture_name_list:
    # child aperture to be constructed
    aperture = pysiaf.JwstAperture()
    aperture.AperName = AperName
    aperture.InstrName = siaf_detector_parameters['InstrName'][0].upper()

    aperture.XDetSize = siaf_detector_parameters['XDetSize'][0]
    aperture.YDetSize = siaf_detector_parameters['YDetSize'][0]
    aperture.AperShape = siaf_detector_parameters['AperShape'][0]
    # aperture.DetSciParity = 1

    aperture_definitions_index = siaf_aperture_definitions['AperName'].tolist().index(AperName)
    # Retrieve basic aperture parameters from definition files
    for attribute in 'XDetRef YDetRef AperType XSciSize YSciSize XSciRef YSciRef'.split():
        # setattr(aperture, attribute, getattr(parent_aperture, attribute))
        setattr(aperture, attribute, siaf_aperture_definitions[attribute][aperture_definitions_index])

    aperture.DDCName = 'not set'
    aperture.Comment = None
    aperture.UseAfterDate = '2014-01-01'


    if aperture.AperType == 'OSS':
        aperture.DetSciYAngle = 0
        aperture.DetSciParity = 1
        aperture.VIdlParity = 1


    if AperName in ['FGS1_FULL', 'FGS1_FULL_OSS', 'FGS2_FULL', 'FGS2_FULL_OSS']:
        if AperName in detector_layout['AperName']:
            detector_layout_index = detector_layout['AperName'].tolist().index(AperName)
            for attribute in 'DetSciYAngle DetSciParity VIdlParity'.split():
                setattr(aperture, attribute, detector_layout[attribute][detector_layout_index])

        index = siaf_alignment_parameters['AperName'].tolist().index(AperName)
        aperture.V3SciYAngle = siaf_alignment_parameters['V3SciYAngle'][index]
        aperture.V3SciXAngle = siaf_alignment_parameters['V3SciXAngle'][index]
        aperture.V3IdlYAngle = siaf_alignment_parameters['V3IdlYAngle'][index]

        for attribute_name in 'V2Ref V3Ref'.split():
            setattr(aperture, attribute_name, siaf_alignment_parameters[attribute_name][index])

        polynomial_coefficients = iando.read.read_siaf_distortion_coefficients(instrument, AperName)

        number_of_coefficients = len(polynomial_coefficients)
        polynomial_degree = np.int((np.sqrt(8 * number_of_coefficients + 1) - 3) / 2)

        # set polynomial coefficients
        siaf_indices = ['{:02d}'.format(d) for d in polynomial_coefficients['siaf_index'].tolist()]
        for i in range(polynomial_degree + 1):
            for j in np.arange(i + 1):
                row_index = siaf_indices.index('{:d}{:d}'.format(i, j))
                for colname in 'Sci2IdlX Sci2IdlY Idl2SciX Idl2SciY'.split():
                    setattr(aperture, '{}{:d}{:d}'.format(colname, i, j), polynomial_coefficients[colname][row_index])

        aperture.Sci2IdlDeg = polynomial_degree
        aperture.complement()

    aperture_dict[AperName] = aperture

#second pass to set parameters for apertures that depend on other apertures
for AperName in aperture_name_list:
    index = siaf_aperture_definitions['AperName'].tolist().index(AperName)
    aperture = aperture_dict[AperName]

    if (siaf_aperture_definitions['parent_apertures'][index] is not None) and (siaf_aperture_definitions['dependency_type'][index] == 'default'):

        aperture._parent_apertures = siaf_aperture_definitions['parent_apertures'][index]
        parent_aperture = aperture_dict[aperture._parent_apertures]

        for attribute in 'V3SciYAngle V3SciXAngle DetSciYAngle Sci2IdlDeg DetSciParity ' \
                         'VIdlParity'.split():
            setattr(aperture, attribute, getattr(parent_aperture, attribute))


        aperture.V3IdlYAngle = tools.v3sciyangle_to_v3idlyangle(aperture.V3SciYAngle)
        # aperture.V3IdlYAngle = aperture.V3SciYAngle

        aperture = tools.set_reference_point_and_distortion(instrument, aperture, parent_aperture)

        if 0:

            # see calc worksheet in SIAFEXCEL
            xsci_offset = (aperture.XDetRef - parent_aperture.XDetRef) * np.cos(np.deg2rad(aperture.DetSciYAngle))
            ysci_offset = (aperture.YDetRef - parent_aperture.YDetRef) * np.cos(np.deg2rad(aperture.DetSciYAngle))

            # shift polynomial coefficients of the parent aperture
            k = 0
            sci2idlx_coefficients = np.zeros(number_of_coefficients)
            sci2idly_coefficients = np.zeros(number_of_coefficients)
            idl2scix_coefficients = np.zeros(number_of_coefficients)
            idl2sciy_coefficients = np.zeros(number_of_coefficients)
            for i in range(polynomial_degree + 1):
                for j in np.arange(i + 1):
                    sci2idlx_coefficients[k] = getattr(parent_aperture, 'Sci2IdlX{:d}{:d}'.format(i, j))
                    sci2idly_coefficients[k] = getattr(parent_aperture, 'Sci2IdlY{:d}{:d}'.format(i, j))
                    idl2scix_coefficients[k] = getattr(parent_aperture, 'Idl2SciX{:d}{:d}'.format(i, j))
                    idl2sciy_coefficients[k] = getattr(parent_aperture, 'Idl2SciY{:d}{:d}'.format(i, j))
                    k += 1

            sci2idlx_coefficients_shifted = polynomial.shift_coefficients(sci2idlx_coefficients, xsci_offset, ysci_offset, order=4, verbose=False)
            sci2idly_coefficients_shifted = polynomial.shift_coefficients(sci2idly_coefficients, xsci_offset, ysci_offset, order=4, verbose=False)

            # see calc worksheet in SIAFEXCEL
            dx_idl = sci2idlx_coefficients_shifted[0]
            dy_idl = sci2idly_coefficients_shifted[0]

            # remove the zero point offsets from the coefficients
            idl2scix_coefficients_shifted = polynomial.shift_coefficients(idl2scix_coefficients, dx_idl, dy_idl, order=4, verbose=False)
            idl2sciy_coefficients_shifted = polynomial.shift_coefficients(idl2sciy_coefficients, dx_idl, dy_idl, order=4, verbose=False)

            # set 00 coefficient to zero
            sci2idlx_coefficients_shifted[0] = 0
            sci2idly_coefficients_shifted[0] = 0
            idl2scix_coefficients_shifted[0] = 0
            idl2sciy_coefficients_shifted[0] = 0

            # set polynomial coefficients
            k = 0
            for i in range(polynomial_degree + 1):
                for j in np.arange(i + 1):
                    setattr(aperture, 'Sci2IdlX{:d}{:d}'.format(i, j), sci2idlx_coefficients_shifted[k])
                    setattr(aperture, 'Sci2IdlY{:d}{:d}'.format(i, j), sci2idly_coefficients_shifted[k])
                    setattr(aperture, 'Idl2SciX{:d}{:d}'.format(i, j), idl2scix_coefficients_shifted[k])
                    setattr(aperture, 'Idl2SciY{:d}{:d}'.format(i, j), idl2sciy_coefficients_shifted[k])
                    k += 1

            # set V2ref and V3Ref (this is a standard process for child apertures and should be generalized in a function)
            aperture.V2Ref = parent_aperture.V2Ref + aperture.VIdlParity * dx_idl * np.cos(np.deg2rad(aperture.V3IdlYAngle)) + dy_idl * np.sin(np.deg2rad(aperture.V3IdlYAngle))
            aperture.V3Ref = parent_aperture.V3Ref - aperture.VIdlParity * dx_idl * np.sin(np.deg2rad(aperture.V3IdlYAngle)) + dy_idl * np.cos(np.deg2rad(aperture.V3IdlYAngle))


    aperture.complement()

    aperture_dict[AperName] = aperture


#sort SIAF entries in the order of the aperture definition file
aperture_dict = OrderedDict(sorted(aperture_dict.items(), key=lambda t: aperture_name_list.index(t[0])))

if 1:
    #third pass to set DDCNames apertures, which depend on other apertures
    ddc_siaf_aperture_names = np.array([key for key in ddc_apername_mapping.keys()])
    ddc_v2 = np.array([aperture_dict[aperture_name].V2Ref for aperture_name in ddc_siaf_aperture_names])
    ddc_v3 = np.array([aperture_dict[aperture_name].V3Ref for aperture_name in ddc_siaf_aperture_names])
    for AperName in aperture_name_list:
        if aperture_dict[AperName].AperType not in ['TRANSFORM']:
            separation_tel_from_ddc_aperture = np.sqrt((aperture_dict[AperName].V2Ref - ddc_v2)**2 + (aperture_dict[AperName].V3Ref - ddc_v3)**2)
            aperture_dict[AperName].DDCName = ddc_apername_mapping[ddc_siaf_aperture_names[np.argmin(separation_tel_from_ddc_aperture)]]

aperture_collection = pysiaf.ApertureCollection(aperture_dict)

# write the SIAFXML to disk
[filename] = pysiaf.iando.write.write_jwst_siaf(aperture_collection, basepath=test_dir, file_format=['xml'])
print('SIAFXML written in {}'.format(filename))

# compare to SIAFXML produced the old way
# ref_siaf = pysiaf.Siaf(instrument, os.path.join(test_dir, 'FGS_SIAF_2018-04-17.xml'))
ref_siaf = pysiaf.Siaf(instrument)
new_siaf = pysiaf.Siaf(instrument, filename)

# comparison_aperture_names = [AperName for AperName in aperture_name_list if 'NRS_IFU' in AperName]
# comparison_aperture_names = [AperName for AperName, aperture in aperture_dict.items() if aperture.AperType == 'SLIT']
# comparison_aperture_names = [AperName for AperName, aperture in aperture_dict.items() if aperture.AperType in ['FULLSCA', 'OSS']]
# comparison_aperture_names = [AperName for AperName, aperture in aperture_dict.items() if aperture.AperType in ['FULLSCA', 'OSS']]
# comparison_aperture_names = pcf_file_mapping.keys()

comparison_aperture_names = ['FGS1_FULL', 'FGS1_FULL_OSS', 'FGS2_FULL', 'FGS2_FULL_OSS', 'FGS2_SUB32DIAG']
# comparison_aperture_names = ['FGS1_FULL_OSS']
# comparison_aperture_names = ['FGS1_FULL', 'FGS2_FULL']
compare.compare_siaf(new_siaf, reference_siaf_input=ref_siaf, fractional_tolerance=1e-6, selected_aperture_name=comparison_aperture_names)
# 1/0
compare.compare_siaf(new_siaf, reference_siaf_input=ref_siaf, fractional_tolerance=1e-6)
#

