from typing import Union

import numpy as np

from pywavelet.transforms.types import (
    FrequencySeries,
    TimeSeries,
    Wavelet,
    wavelet_dataset,
)

from ... import fft_funcs as fft
from ...logger import logger
from ...utils.wavelet_bins import _get_bins, _preprocess_bins
from ..common import phi_vec, phitilde_vec_norm
from .transform_freq_funcs import transform_wavelet_freq_helper
from .transform_time_funcs import transform_wavelet_time_helper


def from_time_to_wavelet(
    data: TimeSeries, Nf: int = None, Nt: int = None, nx=4.0, mult=32, **kwargs
) -> Wavelet:
    """From time domain data to wavelet domain

    Warning: there can be significant leakage if mult is too small and the
    transform is only approximately exact if mult=Nt/2

    Parameters
    ----------
    data : array_like
        Time domain data
    Nf : int
        Number of frequency bins
    Nt : int
        Number of time bins
    nx : float, optional
        Number of standard deviations for the gaussian wavelet, by default 4.
    mult : int, optional
        Number of time bins to use for the wavelet transform, by default 32
    """
    Nf, Nt = _preprocess_bins(data, Nf, Nt)

    t_bins, f_bins = _get_bins(data, Nf, Nt)

    ND = Nf * Nt
    # enusure exactly this amount of data present
    if len(data) != ND:
        logger.warning(
            f"len(data)={len(data)} != Nf*Nt={ND}. Truncating or padding data."
        )
        data = data[:ND]

    if mult > Nt / 2:
        logger.warning(
            f"mult={mult} is too large for Nt={Nt}. This may lead to bogus results."
        )

    mult = min(mult, Nt // 2)  # make sure K isn't bigger than ND
    phi = phi_vec(Nf, nx, mult)
    wave = transform_wavelet_time_helper(data, Nf, Nt, phi, mult)
    return wavelet_dataset(wave, time_grid=t_bins, freq_grid=f_bins, **kwargs)


def from_time_to_freq_to_wavelet(
    data: TimeSeries, Nf=None, Nt=None, nx=4.0, **kwargs
) -> Wavelet:
    """transform time domain data into wavelet domain via fft and then frequency transform"""
    freqseries = FrequencySeries.from_time_series(data)
    return from_freq_to_wavelet(freqseries, Nf, Nt, nx, **kwargs)


def from_freq_to_wavelet(
    data: FrequencySeries, Nf=None, Nt=None, nx=4.0, **kwargs
) -> Wavelet:
    """do the wavelet transform using the fast wavelet domain transform"""
    Nf, Nt = _preprocess_bins(data, Nf, Nt)
    t_bins, f_bins = _get_bins(data, Nf, Nt)

    phif = 2 / Nf * phitilde_vec_norm(Nf, Nt, nx)
    wave = transform_wavelet_freq_helper(data, Nf, Nt, phif)
    return wavelet_dataset(wave, time_grid=t_bins, freq_grid=f_bins, **kwargs)
