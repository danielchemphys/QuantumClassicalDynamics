import numpy as np
from scipy import fftpack # Tools for fourier transform
from scipy import linalg # Linear algebra for dense matrix


class SplitOpSchrodinger2D:
    """
    The second-order split-operator propagator of the 2D Schrodinger equation in the coordinate representation
    with the time-dependent Hamiltonian H = K(p1, p2, t) + V(x1, x2, t).
    (K and V may not depend on time)
    """
    def __init__(self, **kwargs):
        """
        The following parameters must be specified
            X1_gridDIM, X1_gridDIM - specifying the grid size
            X1_amplitude, X2_amplitude - maximum value of the coordinates

            V(x1, x2) - potential energy (as a function) may depend on time
            diff_V_x1(x1, x2) (optional)
             and
            diff_V_x2(x1, x2) (optional) -- the potential energy gradianet for the Ehrenfest theorem calculations

            K(p1, p2) - momentum dependent part of the hamiltonian (as a function) may depend on time
            diff_K_p1(p1, p2) (optional)
             and
            diff_K_p2(p1, p2) (optionla) -- the kinetic energy gradient for the Ehrenfest theorem calculations

            dt - time step
            t (optional) - initial value of time
        """

        # save all attributes
        for name, value in kwargs.items():
            setattr(self, name, value)

        # Check that all attributes were specified
        try:
            self.X1_gridDIM
            self.X1_gridDIM
        except AttributeError:
            raise AttributeError("Grid sizes (X1_gridDIM and/or X2_gridDIM) was not specified")

        try:
            self.X1_amplitude
            self.X2_amplitude
        except AttributeError:
            raise AttributeError("Coordinate ranges (X1_amplitude and/or X2_amplitude) was not specified")

        try:
            self.V
        except AttributeError:
            raise AttributeError("Potential energy (V) was not specified")

        try:
            self.K
        except AttributeError:
            raise AttributeError("Momentum dependence (K) was not specified")

        try:
            self.dt
        except AttributeError:
            raise AttributeError("Time-step (dt) was not specified")

        try:
            self.t
        except AttributeError:
            print("Warning: Initial time (t) was not specified, thus it is set to zero.")
            self.t = 0.

        # get coordinate step sizes
        self.dX1 = 2.*self.X1_amplitude / self.X1_gridDIM
        self.dX2 = 2.*self.X2_amplitude / self.X2_gridDIM

        # generate coordinate ranges
        self.X1 = np.linspace(-self.X1_amplitude, self.X1_amplitude - self.dX1 , self.X1_gridDIM)
        self.X1 = self.X1[:, np.newaxis]
        # see http://docs.scipy.org/doc/numpy/reference/arrays.indexing.html
        # for explanation of np.newaxis and other array indexing operations
        # also http://docs.scipy.org/doc/numpy-1.10.1/user/basics.broadcasting.html
        # for understanding the broadcasting in array operations

        self.X2 = np.linspace(-self.X2_amplitude, self.X2_amplitude - self.dX2 , self.X2_gridDIM)
        self.X2 = self.X2[np.newaxis,:]

        # generate momentum ranges and step sizes as it corresponds to FFT frequencies
        self.P1 = fftpack.fftfreq(self.X1_gridDIM, self.dX1/(2*np.pi))
        self.dP1 = self.P1[1] - self.P1[0]
        self.P1 = self.P1[:, np.newaxis]

        self.P2 = fftpack.fftfreq(self.X2_gridDIM, self.dX2/(2*np.pi))
        self.dP2 = self.P2[1] - self.P2[0]
        self.P2 = self.P2[np.newaxis,:]

        try:
            # Pre-calculate the exponent, if the potential is time independent
            self._expV = np.exp(-self.dt*0.5j*self.V(self.X1, self.X2))
        except TypeError:
            # If exception is generated, then the potential is time-dependent
            # and caching is not possible
            pass

        try:
            # Pre-calculate the exponent, if the kinetic energy is time independent
            self._expK = np.exp(-self.dt*1j*self.K(self.P1, self.P2))
        except TypeError:
            # If exception is generated, then the kinetic energy is time-dependent
            # and caching is not possible
            pass

        # Check whether the necessary terms are specified to calculate the Ehrenfest theorems
        try:
            # Pre-calculate RHS if time independent
            try:
                self._diff_V_x1 = self.diff_V_x1(self.X1, self.X2)
            except TypeError:
                pass
            try:
                self._diff_V_x2 = self.diff_V_x2(self.X1, self.X2)
            except TypeError:
                pass
            try:
                self._diff_K_p1 = self.diff_K_p1(self.P1, self.P2)
            except TypeError:
                pass
            try:
                self._diff_K_p2 = self.diff_K_p2(self.P1, self.P2)
            except TypeError:
                pass

            # Pre-calculate the potential and kinetic energies for
            # calculating the expectation value of Hamiltonian
            try:
                self._V = self.V(self.X1, self.X2)
            except TypeError:
                pass
            try:
                self._K = self.K(self.P1, self.P2)
            except TypeError:
                pass

            # Lists where the expectation values of X and P
            self.X1_average = []
            self.P1_average = []
            self.X2_average = []
            self.P2_average = []

            # Lists where the right hand sides of the Ehrenfest theorems for X and P
            self.X1_average_RHS = []
            self.P1_average_RHS = []
            self.X2_average_RHS = []
            self.P2_average_RHS = []

            # List where the expectation value of the Hamiltonian will be calculated
            self.hamiltonian_average = []

            # Flag requesting tha the Ehrenfest theorem calculations
            self.isEhrenfest = True
        except AttributeError:
            # Since self.diff_V and self.diff_K are not specified,
            # the Ehrenfest theorem will not be calculated
            self.isEhrenfest = False

    def propagate(self, time_steps=1):
        """
        Time propagate the wave function saved in self.wavefunction
        :param time_steps: number of self.dt time increments to make
        :return: self.wavefunction
        """

        # pre-compute the sqrt of the volume element
        sqrtdX1dX2 = np.sqrt(self.dX1 * self.dX2)

        for _ in xrange(time_steps):

            expV = self.get_expV(self.t)
            self.wavefunction *= expV

            # going to the momentum representation
            self.wavefunction = fftpack.fft2(self.wavefunction, overwrite_x=True)
            self.wavefunction *= self.get_expK(self.t)

            # going back to the coordinate representation
            self.wavefunction = fftpack.ifft2(self.wavefunction, overwrite_x=True)
            self.wavefunction *= expV

            # normalize
            # this line is equivalent to
            # self.wavefunction /= np.sqrt(np.sum(np.abs(self.wavefunction)**2)*self.dX1*self.dX1)
            self.wavefunction /= linalg.norm(np.ravel(self.wavefunction)) * sqrtdX1dX2

            # calculate the Ehrenfest theorems
            self.get_Ehrenfest(self.t)

            # increment current time
            self.t += self.dt

        return self.wavefunction

    def get_Ehrenfest(self, t):
        """
        Calculate observables entering the Ehrenfest theorems at time (t)
        """
        if self.isEhrenfest:
            # calculate the coordinate density
            density_coord = np.abs(self.wavefunction)**2
            # normalize
            density_coord /= density_coord.sum()

            # save the current value of coordinate-dependent observables
            self.X1_average.append(
                np.sum(density_coord * self.X1)
            )
            self.X2_average.append(
                np.sum(density_coord * self.X2)
            )
            self.P1_average_RHS.append(
                -np.sum(density_coord * self.get_diff_V_x1(t))
            )
            self.P2_average_RHS.append(
                -np.sum(density_coord * self.get_diff_V_x2(t))
            )

            # calculate density in the momentum representation
            density_momentum = np.abs(fftpack.fft2(self.wavefunction))**2
            # normalize
            density_momentum /= density_momentum.sum()

            # save the current value of momentum-dependent observables
            self.P1_average.append(
                np.sum(density_momentum * self.P1)
            )
            self.P2_average.append(
                np.sum(density_momentum * self.P2)
            )
            self.X1_average_RHS.append(
                np.sum(density_momentum * self.get_diff_K_p1(t))
            )
            self.X2_average_RHS.append(
                np.sum(density_momentum * self.get_diff_K_p2(t))
            )

            # save the current expectation value of energy
            self.hamiltonian_average.append(
                np.sum(density_coord * self.get_V(t))
                +
                np.sum(density_momentum * self.get_K(t))
            )


    def get_expV(self, t):
        """
        Return the exponent of the potential energy at time (t)
        """
        try:
            # aces the pre-calculated value
            return self._expV
        except AttributeError:
            # Calculate result = np.exp(-self.dt*1j * self.V(self.X1, self.X2, t))
            # in efficient way
            result = -self.dt*0.5j*self.V(self.X1, self.X2, t)
            return np.exp(result, out=result)

    def get_expK(self, t):
        """
        Return the exponent of the kinetic energy at time (t)
        """
        try:
            # aces the pre-calculated value
            return self._expK
        except AttributeError:
            # Calculate result = np.exp(*self.K(self.P1, self.P2, t))
            result = -self.dt*1j*self.K(self.P1, self.P2, t)
            return np.exp(result, out=result)

    def get_diff_V_x1(self, t):
        """
        Return the RHS (x1) for the Ehrenfest theorem at time (t)
        """
        try:
            # access the pre-calculated value
            return self._diff_V_x1
        except AttributeError:
            return self.diff_V_x1(self.X1, self.X2, t)

    def get_diff_V_x2(self, t):
        """
        Return the RHS (x2) for the Ehrenfest theorem at time (t)
        """
        try:
            # access the pre-calculated value
            return self._diff_V_x2
        except AttributeError:
            return self.diff_V_x2(self.X1, self.X2, t)

    def get_diff_K_p1(self, t):
        """
        Return the RHS (p1) for the Ehrenfest theorem at time (t)
        """
        try:
            # access the pre-calculated value
            return self._diff_K_p1
        except AttributeError:
            return self.diff_K_p1(self.P1, self.P2, t)

    def get_diff_K_p2(self, t):
        """
        Return the RHS (p2) for the Ehrenfest theorem at time (t)
        """
        try:
            # access the pre-calculated value
            return self._diff_K_p2
        except AttributeError:
            return self.diff_K_p2(self.P1, self.P2, t)

    def get_K(self, t):
        """
        Return the kinetic energy at time (t)
        """
        try:
            return self._K
        except AttributeError:
            return self.K(self.P1, self.P2, t)

    def get_V(self, t):
        """
        Return the potential energy at time (t)
        """
        try:
            return self._V
        except AttributeError:
            return self.V(self.X1, self.X2, t)

    def set_wavefunction(self, wavefunc):
        """
        Set the initial wave function
        :param wavefunc: 2D numoy array contaning the wave function
        :return: self
        """
        # perform the consistency checks
        assert wavefunc.shape == (self.X1.size, self.X2.size), \
            "The grid size does not match with the wave function"

        # make sure the wavefunction is stored as a complex array
        self.wavefunction = wavefunc + 0j

        # normalize
        self.wavefunction /= linalg.norm(np.ravel(self.wavefunction)) * np.sqrt(self.dX1*self.dX2)

        return self

##############################################################################
#
#   Run some examples
#
##############################################################################

if __name__ == '__main__':

    # load tools for creating animation
    import sys

    if sys.platform == 'darwin':
        # only for MacOS
        import matplotlib
        matplotlib.use('TKAgg')

    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    # Use the documentation string for the developed class
    print(SplitOpSchrodinger2D.__doc__)

    class VisualizeDynamics2D:
        """
        Class to visualize the wave function dynamics in 2D.
        """
        def __init__(self, fig):
            """
            Initialize all propagators and frame
            :param fig: matplotlib figure object
            """
            #  Initialize systems
            self.set_quantum_sys()

            #################################################################
            #
            # Initialize plotting facility
            #
            #################################################################

            self.fig = fig

            ax = fig.add_subplot(111)

            ax.set_title('Wavefunction density, $| \\Psi(x_1, x_2, t) |^2$')
            extent=[self.quant_sys.X2.min(), self.quant_sys.X2.max(), self.quant_sys.X1.min(), self.quant_sys.X1.max()]
            self.img = ax.imshow([[]], extent=extent, origin='lower')

            self.fig.colorbar(self.img)

            ax.set_xlabel('$x_2$ (a.u.)')
            ax.set_ylabel('$x_1$ (a.u.)')

        def set_quantum_sys(self):
            """
            Initialize quantum propagator
            :param self:
            :return:
            """
            self.quant_sys = SplitOpSchrodinger2D(
                t=0.,
                dt=0.005,
                X1_gridDIM=256,
                X1_amplitude=5.,
                X2_gridDIM=256,
                X2_amplitude=5.,

                # kinetic energy part of the hamiltonian
                K=lambda p1, p2: 0.5*(p1**2 + p2**2),
                # these functions are used for evaluating the Ehrenfest theorems
                diff_K_p1=lambda p1, p2: p1,
                diff_K_p2=lambda p1, p2: p2,

                # potential energy part of the hamiltonian
                V=lambda x1, x2: 0.5*(3)**2*(x1**2 + x2**2),
                # these functions are used for evaluating the Ehrenfest theorems
                diff_V_x1=lambda x1, x2: 3**2 * x1,
                diff_V_x2=lambda x1, x2: 3**2 * x2,
            )
            # set randomised initial condition
            self.quant_sys.set_wavefunction(
                np.exp(
                    # randomized positions
                    -np.random.uniform(0.5, 3.)*(self.quant_sys.X1 + np.random.uniform(-2., 2.))**2
                    -np.random.uniform(0.5, 3.)*(self.quant_sys.X2 + np.random.uniform(-2., 2.))**2
                    # randomized initial velocities
                    -1j*np.random.uniform(-2., 2.)*self.quant_sys.X1
                    -1j*np.random.uniform(-2., 2.)*self.quant_sys.X2
                )
            )

        def empty_frame(self):
            """
            Make empty frame and reinitialize quantum system
            :param self:
            :return: image object
            """
            self.set_quantum_sys()
            self.img.set_array([[]])
            return self.img,

        def __call__(self, frame_num):
            """
            Draw a new frame
            :param frame_num: current frame number
            :return: image objects
            """
            # propagate and set the density
            self.img.set_array(
                np.abs(self.quant_sys.propagate(20))**2
            )
            return self.img,

    fig = plt.gcf()
    visualizer = VisualizeDynamics2D(fig)
    animation = FuncAnimation(fig, visualizer, frames=np.arange(100),
                              init_func=visualizer.empty_frame, repeat=True, blit=True)
    plt.show()

    # extract the reference to quantum system
    quant_sys = visualizer.quant_sys

    # Analyze how well the energy was preseved
    h = np.array(quant_sys.hamiltonian_average)
    print(
        "\nHamiltonian is preserved within the accuracy of %f percent" % ((1. - h.min()/h.max())*100)
    )

    #################################################################
    #
    # Plot the Ehrenfest theorems after the animation is over
    #
    #################################################################

    # generate time step grid
    dt = quant_sys.dt
    times = np.arange(dt, dt + dt*len(quant_sys.X1_average), dt)

    plt.subplot(121)
    plt.title("The first Ehrenfest theorem verification")

    plt.plot(times, np.gradient(quant_sys.X1_average, dt), 'r-', label='$d\\langle \\hat{x}_1 \\rangle/dt$')
    plt.plot(times, quant_sys.X1_average_RHS, 'b--', label='$\\langle \\hat{p}_1 \\rangle$')

    plt.plot(times, np.gradient(quant_sys.X2_average, dt), 'g-', label='$d\\langle \\hat{x}_2 \\rangle/dt$')
    plt.plot(times, quant_sys.X2_average_RHS,  'k--', label='$\\langle \\hat{p}_2 \\rangle$')

    plt.legend()
    plt.xlabel('time $t$ (a.u.)')

    plt.subplot(122)
    plt.title("The second Ehrenfest theorem verification")

    plt.plot(times, np.gradient(quant_sys.P1_average, dt), 'r-', label='$d\\langle \\hat{p}_1 \\rangle/dt$')
    plt.plot(times, quant_sys.P1_average_RHS, 'b--', label='$\\langle -\\partial\\hat{V}/\\partial\\hat{x}_1 \\rangle$')

    plt.plot(times, np.gradient(quant_sys.P2_average, dt), 'g-', label='$d\\langle \\hat{p}_2 \\rangle/dt$')
    plt.plot(times, quant_sys.P2_average_RHS, 'k--', label='$\\langle -\\partial\\hat{V}/\\partial\\hat{x}_2 \\rangle$')

    plt.legend()
    plt.xlabel('time $t$ (a.u.)')

    plt.show()