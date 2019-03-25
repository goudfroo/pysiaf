#!/usr/bin/env python
"""Tests for the pysiaf aperture classes.

Authors
-------
    Johannes Sahlmann

"""

import numpy as np
import pytest

from ..iando import read
from ..siaf import Siaf, get_jwst_apertures
from ..utils.tools import get_grid_coordinates

@pytest.fixture(scope='module')
def siaf_objects():
    """Return list of Siaf objects."""
    siafs = []
    for instrument in 'NIRCam NIRISS FGS MIRI'.split():
        siaf = Siaf(instrument)
        siafs.append(siaf)
    return siafs


def test_idl_to_tel(verbose=True):
    """Test the transformations between ideal and telescope frames that do not use the planar approximation."""
    siaf = Siaf('NIRISS')
    # siaf = Siaf('HST')

    x_idl, y_idl = get_grid_coordinates(10, (0, 0), 100)

    for aper_name in siaf.apertures.keys():
    # for aper_name in 'FGS1 FGS2 FGS3'.split():
        aperture = siaf[aper_name]

        # for idl_to_tel_method in ['planar_approximation', 'spherical_transformation', 'spherical']:
        for idl_to_tel_method in ['planar_approximation' 'spherical']:
        # for idl_to_tel_method in ['planar_approximation']:
        # for idl_to_tel_method in ['spherical']:
            if idl_to_tel_method == 'spherical_transformation':
                input_coordinate_types = ['tangent_plane', 'spherical']
            elif idl_to_tel_method == 'spherical':
                input_coordinate_types = ['polar', 'cartesian']
            else:
                input_coordinate_types = ['tangent_plane']

            for input_coordinates in input_coordinate_types:
                # print(x_idl, y_idl)
                v2, v3 = aperture.idl_to_tel(x_idl, y_idl, method=idl_to_tel_method, input_coordinates=input_coordinates, output_coordinates=input_coordinates)
                # print(v2, v3)
                x_idl_2, y_idl_2 = aperture.tel_to_idl(v2, v3, method=idl_to_tel_method, input_coordinates=input_coordinates, output_coordinates=input_coordinates)
                # print(x_idl_2, y_idl_2)
                x_diff = np.abs(x_idl - x_idl_2)
                y_diff = np.abs(y_idl - y_idl_2)
                if verbose:
                    print('{} {}: Aperture {} {} x_diff {} y_diff {}'.format(idl_to_tel_method, input_coordinates, aper_name, input_coordinates, np.max(x_diff), np.max(y_diff)))
                if idl_to_tel_method == 'spherical_transformation':
                    if input_coordinates == 'spherical':
                        threshold = 6e-13
                    elif input_coordinates == 'tangent_plane':
                        threshold = 5e-10
                elif idl_to_tel_method == 'planar_approximation':
                    threshold = 7e-14
                elif idl_to_tel_method == 'spherical':
                    if input_coordinates == 'polar':
                        threshold = 6e-13
                    elif input_coordinates == 'cartesian':
                        threshold = 5e-8
                assert np.max(x_diff) < threshold
                assert np.max(y_diff) < threshold


def test_hst_fgs_idl_to_tel(verbose=True):
    """Test the transformations between ideal and telescope frames."""

    siaf = Siaf('HST')

    x_idl, y_idl = get_grid_coordinates(2, (0, -50), 1000, y_width=400)

    for aper_name in 'FGS1 FGS2 FGS3'.split():
        aperture = siaf[aper_name]
        for idl_to_tel_method in ['planar_approximation', 'spherical']:
            if idl_to_tel_method == 'spherical':
                input_coordinate_types = ['polar', 'cartesian']
            else:
                input_coordinate_types = ['tangent_plane']

            for input_coordinates in input_coordinate_types:
                if input_coordinates == 'polar':
                    v2, v3 = aperture.idl_to_tel(x_idl, y_idl, method=idl_to_tel_method,
                                                 input_coordinates='cartesian',
                                                 output_coordinates=input_coordinates)
                    x_idl_2, y_idl_2 = aperture.tel_to_idl(v2, v3, method=idl_to_tel_method,
                                                           input_coordinates=input_coordinates,
                                                           output_coordinates='cartesian')
                else:
                    v2, v3 = aperture.idl_to_tel(x_idl, y_idl, method=idl_to_tel_method, input_coordinates=input_coordinates, output_coordinates=input_coordinates)
                    x_idl_2, y_idl_2 = aperture.tel_to_idl(v2, v3, method=idl_to_tel_method, input_coordinates=input_coordinates, output_coordinates=input_coordinates)
                x_diff = np.abs(x_idl - x_idl_2)
                y_diff = np.abs(y_idl - y_idl_2)
                if verbose:
                    print('{} {}: Aperture {} {} x_diff {} y_diff {}'.format(idl_to_tel_method, input_coordinates, aper_name, input_coordinates, np.max(x_diff), np.max(y_diff)))

                threshold = 2e-13

                assert np.max(x_diff) < threshold
                assert np.max(y_diff) < threshold


def test_jwst_aperture_transforms(siaf_objects, verbose=False, threshold=None):
    """Test transformations between frames.

    Transform back and forth between frames and verify that input==output.

    Parameters
    ----------
    siaf_objects
    verbose

    """
    labels = ['X', 'Y']


    from_frame = 'sci'
    to_frames = 'det idl tel'.split()

    x_sci = np.linspace(-10, 10, 3)
    y_sci = np.linspace(10, -10, 3)

    for siaf in siaf_objects:
        if threshold is None:
            if siaf.instrument in ['miri']:
                threshold = 0.04
            elif siaf.instrument in ['nircam']:
                threshold = 42.
            else:
                threshold = 0.1
        for aper_name in siaf.apertures.keys():
            skip = False

            # aperture
            aperture = siaf[aper_name]

            if (aperture.AperType in ['COMPOUND', 'TRANSFORM']) or (
                    siaf.instrument in ['nircam', 'miri', 'nirspec'] and
                    aperture.AperType == 'SLIT'):
                skip = True

            if skip is False:
                # test transformations
                if verbose:
                    print('testing {} {}'.format(siaf.instrument, aper_name))

                for to_frame in to_frames:
                    forward_transform = getattr(aperture, '{}_to_{}'.format(from_frame, to_frame))
                    backward_transform = getattr(aperture, '{}_to_{}'.format(to_frame, from_frame))

                    x_out, y_out = backward_transform(*forward_transform(x_sci, y_sci))
                    x_mean_error = np.mean(np.abs(x_sci - x_out))
                    y_mean_error = np.mean(np.abs(y_sci - y_out))
                    x_rms_error = np.std(np.abs(x_sci - x_out))
                    y_rms_error = np.std(np.abs(y_sci - y_out))
                    for i, error in enumerate([x_mean_error, y_mean_error]):
                        if verbose:
                            print('{} {}: mean absolute error in {}<->{} {}-transform is {:02.6f})'.format(
                                siaf.instrument, aper_name, from_frame, to_frame, labels[i], error))
                        assert error < threshold
                    for i, error in enumerate([x_rms_error, y_rms_error]):
                        if verbose:
                            print('{} {}:  rms absolute error in {}<->{} {}-transform is {:02.6f})'.format(
                                siaf.instrument, aper_name, from_frame, to_frame, labels[i], error))
                        assert error < threshold


def test_jwst_aperture_vertices(siaf_objects):
    """Test the JwstAperture vertices by rederiving them and comparing to SIAF.

    Rederive Idl vertices and compare with content of SIAFXML

    """
    verbose = False

    threshold = 0.2
    labels = ['X', 'Y']

    for siaf in siaf_objects:
        for aper_name in siaf.apertures.keys():
            skip = False

            #aperture
            aperture = siaf[aper_name]

            if (aperture.AperType in ['COMPOUND', 'TRANSFORM']) or \
                    (siaf.instrument in ['nircam', 'miri', 'nirspec']
                     and aperture.AperType == 'SLIT'):
                skip = True

            if skip is False:
                if verbose:
                    print('testing {} {}'.format(siaf.instrument, aper_name))

                # Idl corners from Sci attributes (XSciRef, XSciSize etc.)
                x_idl_vertices_rederived, y_idl_vertices_rederived = aperture.corners('idl',
                                                                                      rederive=True)

                # Idl corners from SIAFXML
                x_idl_vertices = np.array([getattr(aperture, 'XIdlVert{:d}'.format(j)) for j in [1, 2, 3, 4]])
                y_idl_vertices = np.array([getattr(aperture, 'YIdlVert{:d}'.format(j)) for j in [1, 2, 3, 4]])

                if verbose:
                    print(x_idl_vertices, x_idl_vertices_rederived)
                    print(y_idl_vertices, y_idl_vertices_rederived)

                x_mean_error = np.abs(np.mean(x_idl_vertices) - np.mean(x_idl_vertices_rederived))
                y_mean_error = np.abs(np.mean(y_idl_vertices) - np.mean(y_idl_vertices_rederived))

                if verbose:
                    for i, error in enumerate([x_mean_error, y_mean_error]):
                        print('{} {}: Error in {}Idl_vertices is {:02.6f})'.format(siaf.instrument, aper_name, labels[i], error))

                assert x_mean_error < threshold
                assert y_mean_error < threshold


def test_raw_transformations(verbose=False):
    """Test raw_to_sci and sci_to_raw transformations"""
    siaf_detector_layout = read.read_siaf_detector_layout()
    master_aperture_names = siaf_detector_layout['AperName'].data
    apertures_dict = {'instrument': siaf_detector_layout['InstrName'].data}
    apertures_dict['pattern'] = master_aperture_names
    apertures = get_jwst_apertures(apertures_dict, exact_pattern_match=True)

    grid_amplitude = 2048
    x_raw, y_raw = get_grid_coordinates(10, (grid_amplitude/2, grid_amplitude/2), grid_amplitude)

    labels = ['X', 'Y']
    threshold = 0.1
    from_frame = 'raw'
    to_frame = 'sci'

    # compute roundtrip error
    for aper_name, aperture in apertures.apertures.items():
        forward_transform = getattr(aperture, '{}_to_{}'.format(from_frame, to_frame))
        backward_transform = getattr(aperture, '{}_to_{}'.format(to_frame, from_frame))

        x_out, y_out = backward_transform(*forward_transform(x_raw, y_raw))
        x_mean_error = np.mean(np.abs(x_raw - x_out))
        y_mean_error = np.mean(np.abs(y_raw - y_out))
        for i, error in enumerate([x_mean_error, y_mean_error]):
            if verbose:
                print('{} {}: Error in {}<->{} {}-transform is {:02.6f})'.format(
                    aperture.InstrName, aper_name, from_frame, to_frame, labels[i], error))
            assert error < threshold
