import numpy as np

from ..transforms.types import FrequencySeries, TimeSeries, Wavelet


def periodogram(ts: TimeSeries, wd_func=np.blackman):
    """Compute the periodogram of a time series using the
    Blackman window

    Parameters
    ----------
    ts : ndarray
        intput time series
    wd_func : callable
        tapering window function in the time domain

    Returns
    -------
    ndarray
        periodogram at Fourier frequencies
    """
    fs = ts.sample_rate
    wd = wd_func(ts.data.shape[0])
    k2 = np.sum(wd**2)
    per = np.abs(np.fft.fft(ts.data * wd)) ** 2 * 2 / (k2 * fs)
    freq = np.fft.fftfreq(len(ts)) * fs
    # filter f[f>0]
    mask = freq >= 0
    return FrequencySeries(data=per[mask], freq=freq[mask])


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


def lisa_psd(f, fmin=1e-3):
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


def generate_noise(psd_func, n_data, fs, tmax=432000) -> TimeSeries:
    """
    Noise generator from arbitrary power spectral density.
    Uses a Gaussian random generation in the frequency domain.

    Parameters
    ----------
    psd_func: callable
        one-sided PSD function in A^2 / Hz, where A is the unit of the desired
        output time series. Can also return a p x p spectrum matrix
    n_data: int
        size of output time series
    fs: float
        sampling frequency in Hz


    Returns
    -------
    tseries: ndarray
        generated time series

    """

    # Number of points to generate in the frequency domain (circulant embedding)
    n_psd = 2 * n_data
    # Number of positive frequencies
    n_fft = int((n_psd - 1) / 2)
    # Frequency array
    f = np.fft.fftfreq(n_psd) * fs
    # Avoid zero frequency as it sometimes makes the PSD infinite
    f[0] = f[1]
    # Compute the PSD (or the spectrum matrix)
    psd_f = psd_func(np.abs(f))

    if psd_f.ndim == 1:
        psd_sqrt = np.sqrt(psd_f)
        # Real part of the Noise fft : it is a gaussian random variable
        noise_tf_real = (
            np.sqrt(0.5)
            * psd_sqrt[0 : n_fft + 1]
            * np.random.normal(loc=0.0, scale=1.0, size=n_fft + 1)
        )
        # Imaginary part of the Noise fft :
        noise_tf_im = (
            np.sqrt(0.5)
            * psd_sqrt[0 : n_fft + 1]
            * np.random.normal(loc=0.0, scale=1.0, size=n_fft + 1)
        )
        # The Fourier transform must be real in f = 0
        noise_tf_im[0] = 0.0
        noise_tf_real[0] = noise_tf_real[0] * np.sqrt(2.0)
        # Create the NoiseTF complex numbers for positive frequencies
        noise_tf = noise_tf_real + 1j * noise_tf_im

    # To get a real valued signal we must have NoiseTF(-f) = NoiseTF*
    if (n_psd % 2 == 0) & (psd_f.ndim == 1):
        # The TF at Nyquist frequency must be real in the case of an even
        # number of data
        noise_sym0 = np.array([psd_sqrt[n_fft + 1] * np.random.normal(0, 1)])
        # Add the symmetric part corresponding to negative frequencies
        noise_tf = np.hstack(
            (noise_tf, noise_sym0, np.conj(noise_tf[1 : n_fft + 1])[::-1])
        )
    elif (n_psd % 2 != 0) & (psd_f.ndim == 1):
        noise_tf = np.hstack(
            (noise_tf, np.conj(noise_tf[1 : n_fft + 1])[::-1])
        )

    tseries = np.fft.ifft(np.sqrt(n_psd * fs / 2.0) * noise_tf, axis=0)

    delta_t = 1 / fs  # Sampling interval -- largely oversampling here.
    n_data = 2 ** int(np.log(tmax / delta_t) / np.log(2))
    t = np.arange(0, n_data) * delta_t
    return TimeSeries(data=tseries[0:n_data].real, time=t)



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
    PSD = lisa_psd(freq)

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