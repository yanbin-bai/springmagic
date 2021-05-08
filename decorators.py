import maya.mel as mel
import maya.cmds as cmds

from functools import wraps


# -----------------------------------------------------------------------------
# Decorators
# -----------------------------------------------------------------------------
def viewportOff(func):
    """
    Decorator - turn off Maya display while func is running.
    if func will fail, the error will be raised after.
    """
    @wraps(func)
    def wrap(*args, **kwargs):

        # Turn $gMainPane Off:
        mel.eval("paneLayout -e -manage false $gMainPane")

        # Decorator will try/except running the function.
        # But it will always turn on the viewport at the end.
        # In case the function failed, it will prevent leaving maya viewport off.
        try:
            return func(*args, **kwargs)
        except Exception:
            raise  # will raise original error
        finally:
            mel.eval("paneLayout -e -manage true $gMainPane")

    return wrap


class gShowProgress(object):
    """
    Function decorator to show the user (progress) feedback.
    @usage

    import time
    @gShowProgress(end=10)
    def createCubes():
        for i in range(10):
            time.sleep(1)
            if createCubes.isInterrupted(): break
            iCube = cmds.polyCube(w=1,h=1,d=1)
            cmds.move(i,i*.2,0,iCube)
            createCubes.step()
    """

    def __init__(self, status='Busy...', start=0, end=100, interruptable=True):
        import maya.mel

        self.mStartValue = start
        self.mEndValue = end
        self.mStatus = status
        self.mInterruptable = interruptable
        self.mMainProgressBar = maya.mel.eval('$tmp = $gMainProgressBar')

    def step(self, inValue=1):
        """Increase step
        @param inValue (int) Step value"""
        cmds.progressBar(self.mMainProgressBar, edit=True, step=inValue)

    def progress(self, inValue):
        """Set progression value
        @param inValue (int) Progress value"""
        cmds.progressBar(self.mMainProgressBar, edit=True, progress=inValue)

    def isInterrupted(self):
        """Check if the user has interrupted the progress
        @return (boolean)"""
        return cmds.progressBar(self.mMainProgressBar, query=True, isCancelled=True)

    def start(self):
        """Start progress"""
        cmds.waitCursor(state=True)
        cmds.progressBar(
            self.mMainProgressBar,
            edit=True,
            beginProgress=True,
            isInterruptable=self.mInterruptable,
            status=self.mStatus,
            minValue=self.mStartValue,
            maxValue=self.mEndValue)
        cmds.refresh()

    def end(self):
        """Mark the progress as ended"""
        cmds.progressBar(self.mMainProgressBar, edit=True, endProgress=True)
        cmds.waitCursor(state=False)

    def __call__(self, inFunction):
        """
        Override call method
        @param inFunction (function) Original function
        @return (function) Wrapped function
        @description
            If there are decorator arguments, __call__() is only called once,
            as part of the decoration process! You can only give it a single argument,
            which is the function object.
        """
        def wrapped_f(*args, **kwargs):
            # Start progress
            self.start()
            # Call original function
            inFunction(*args, **kwargs)
            # End progress
            self.end()

        # Add special methods to the wrapped function
        wrapped_f.step = self.step
        wrapped_f.progress = self.progress
        wrapped_f.isInterrupted = self.isInterrupted

        # Copy over attributes
        wrapped_f.__doc__ = inFunction.__doc__
        wrapped_f.__name__ = inFunction.__name__
        wrapped_f.__module__ = inFunction.__module__

        # Return wrapped function
        return wrapped_f
