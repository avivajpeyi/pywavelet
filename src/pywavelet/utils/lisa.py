import numpy as np

from ..transforms.types import FrequencySeries, TimeSeries, Wavelet
from scipy.signal.windows import tukey
from typing import Tuple



def _lisa_poms_pacc(f):
    """
    PSD obtained from: https://arxiv.org/pdf/1803.01944.pdf
    Removed galactic confusion noise. Non stationary effect.
    """

    L = 2.5 * 10**9  # Length of LISA arm
    f0 = 19.09 * 10**-3

    Poms = ((1.5 * 10**-11) ** 2) * (
        1 + ((2 * 10**-3) / f) ** 4
    )  # Optical Metrology Sensor
    Pacc = (
        (3 * 10**-15) ** 2
        * (1 + (4 * 10**-3 / (10 * f)) ** 2)
        * (1 + (f / (8 * 10**-3)) ** 4)
    )  # Acceleration Noise

    PSD = (
        (10 / (3 * L**2))
        * (Poms + (4 * Pacc) / ((2 * np.pi * f)) ** 4)
        * (1 + 0.6 * (f / f0) ** 2)
    )  # PSD

    return PSD


def lisa_psd_func(f, fmin=1e-3):
    # if isinstance(f, np.ndarray):
    #     out = np.zeros_like(f)
    #     out[f>=fmin] = _lisa_poms_pacc(f[f>fmin])
    #     out[f<fmin] = _lisa_poms_pacc(fmin)
    # elif isinstance(f, float):
    #     if f < fmin:
    #         out = _lisa_poms_pacc(fmin)
    #     else:
    #         out = _lisa_poms_pacc(f)

    out = _lisa_poms_pacc(f) * f**4

    return out






def zero_pad(data):
    """
    This function takes in a vector and zero pads it so it is a power of two.
    We do this for the O(Nlog_{2}N) cost when we work in the frequency domain.
    """
    N = len(data)
    pow_2 = np.ceil(np.log2(N))
    return np.pad(data, (0, int((2 ** pow_2) - N)), "constant")


def FFT(waveform: np.ndarray)-> np.ndarray:
    """
    Here we taper the signal, pad and then compute the FFT. We remove the zeroth frequency bin because
    the PSD (for which the frequency domain waveform is used with) is undefined at f = 0.
    """
    N = len(waveform)
    taper = tukey(N, 0.1)
    waveform_w_pad = zero_pad(waveform * taper)
    return np.fft.rfft(waveform_w_pad)[1:]


def freq_PSD(waveform_t:np.ndarray, delta_t:float)-> Tuple[np.ndarray, np.ndarray]:
    """
    Here we take in a waveform and sample the correct fourier frequencies and output the PSD. There is no
    f = 0 frequency bin because the PSD is undefined there.
    """
    n_t = len(zero_pad(waveform_t))
    freq = np.fft.rfftfreq(n_t, delta_t)[1:]
    PSD = lisa_psd_func(freq)

    return freq, PSD


def inner_prod(sig1_f, sig2_f, PSD, delta_t, N_t):
    # Compute inner product. Useful for likelihood calculations and SNRs.
    return (4 * delta_t / N_t) * np.real(
        sum(np.conjugate(sig1_f) * sig2_f / PSD)
    )


def waveform(a:float, f:float, fdot:float, t:np.ndarray, eps=0):
    """
    This is a function. It takes in a value of the amplitude $a$, frequency $f$ and frequency derivative $\dot{f}
    and a time vector $t$ and spits out whatever is in the return function. Modify amplitude to improve SNR.
    Modify frequency range to also affect SNR but also to see if frequencies of the signal are important
    for the windowing method. We aim to estimate the parameters $a$, $f$ and $\dot{f}$.
    """

    return a * (np.sin((2 * np.pi) * (f * t + 0.5 * fdot * t ** 2)))


def optimal_snr(h_signal_f:np.ndarray, psd_f:np.ndarray, delta_t:float, N_t:int)-> float:
    return np.sqrt(inner_prod(
        h_signal_f, h_signal_f, psd_f, delta_t, N_t
    ))  # Compute optimal matched filtering SNR


def get_lisa_data():
    """
    This function is used to generate the data for the LISA detector. We use the waveform function to generate
    the signal and then use the freq_PSD function to generate the PSD. We then use the FFT function to generate
    the frequency domain waveform. We then compute the optimal SNR.
    """

    a_true = 5e-21
    f_true = 1e-3
    fdot_true = 1e-8

    fs = 2 * f_true  # Sampling rate
    delta_t = np.floor(
        0.01 / fs
    )  # Sampling interval -- largely oversampling here.

    # make t of 2**16 in len
    N_t = 2 ** 17
    t = np.arange(0, N_t * delta_t, delta_t)

    h_signal_t = waveform(a_true, f_true, fdot_true, t)
    f_signal, psd_f = freq_PSD(h_signal_t, delta_t)
    h_signal_f = FFT(h_signal_t)
    snr = optimal_snr(h_signal_f, psd_f, delta_t, N_t)
    return h_signal_t, t, h_signal_f, f_signal, psd_f, snr