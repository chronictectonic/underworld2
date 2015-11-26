#TODO: Drawing Objects to implement
# IsoSurface, IsoSurfaceCrossSection
# MeshSurface/MeshSampler (surface/volumes using MeshCrossSection sampler)
# Contour, ContourCrossSection
# HistoricalSwarmTrajectory
# VectorArrowMeshCrossSection?
#
# Maybe later...
# TextureMap
# SwarmShapes, SwarmRGB, SwarmVectors
# EigenVectors, EigenVectorCrossSection
# FeVariableSurface
import underworld
import underworld._stgermain as _stgermain
import underworld.fevariable as fevariable
import underworld.swarm as swarmMod
import underworld.mesh as uwmesh
from underworld.function import Function as _Function
from libUnderworld import *

class ColourMap(_stgermain.StgCompoundComponent):
    _selfObjectName = "_cm"
    _objectsDict = { "_cm": "lucColourMap" }
    
    #Default is a cool-warm map with low variance in luminosity/lightness
    def __init__(self, colours="#288FD0 #50B6B8 #989878 #C68838 #FF7520".split(), logScale=False, discrete=False, **kwargs):
    
        if not isinstance(colours,(str,list)):
            raise TypeError("'colours' object passed in must be of python type 'str' or 'list'")
        if isinstance(colours,(str)):
            self._colours = colours.split()
        else:
            self._colours = colours

        if kwargs.has_key('valueRange'):
            valueRange = kwargs.get('valueRange')
            # is valueRange correctly defined, ie list of length 2 made of numbers
            if not isinstance( valueRange, (list,tuple)):
                raise TypeError("'valueRange' objected passed in must be of type 'list' or 'tuple'")
            if len(valueRange) != 2:
                raise ValueError("'valueRange' must have 2 real values")
            for item in valueRange:
                if not isinstance( item, (int, float) ):
                    raise TypeError("'valueRange' must contain real numbers")
            if not valueRange[0] < valueRange[1]:
                raise ValueError("The first number of the valueRange list must be smaller than the second number")

            # valueRange arg is good - turn off dynamicRange and use input 
            self._dynamicRange=False
            self._valueRange = valueRange
        else:
           self._dynamicRange=True
           self._valueRange = [0.0,1.0] # dummy value - not important

        if not isinstance(logScale, bool):
            raise TypeError("'logScale' parameter must be of 'bool' type.")
        self._logScale = logScale

        if not isinstance(discrete, bool):
            raise TypeError("'discrete' parameter must be of 'bool' type.")
        self._discrete = discrete

        # build parent
        super(ColourMap,self).__init__()

    def _add_to_stg_dict(self,componentDictionary):

        # call parents method
        super(ColourMap,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._cm.name].update( {
            "colours"       :" ".join(self.colours),
            "logScale"      :self._logScale,
            "discrete"      :self._discrete,
            "maximum"       :self._valueRange[1],
            "minimum"       :self._valueRange[0],
            "dynamicRange"  :self._dynamicRange
        } )

    @property
    def valueRange(self):
        """     valueRange (list) : list of 2 numbers that define the min and max of the colour map values 
        """
        return self._valueRange

    @property
    def dynamicRange(self):
        """     dynamicRange (bool) : if True the max and min values of the field will automatically define the colour map value 
                                      range and the valueRange list is ignored. If False the valueRange is used to define the 
                                      colour map value range
        """
        return self._dynamicRange

    @property
    def colours(self):
        """    colours (list): list of colours to use.  Should be provided as a list or a string.
        """
        return self._colours

    @property
    def logScale(self):
        """    logScale (bool): Use a logarithm scale for the colourmap.
        """
        return self._logScale

class Drawing(_stgermain.StgCompoundComponent):
    _selfObjectName = "_dr"
    #This is the base class for all drawing objects but can also be instantiated as is for direct/custom drawing 
    _objectsDict = { "_dr": "lucDrawingObject" } # child should replace _dr with own derived type

    _defaultColourMap = ColourMap()
    
    def __init__(self, colours=None, colourMap=None, properties=None, opacity=-1, colourBar=False, **kwargs):
        if colourMap:
            self._colourMap = colourMap
        elif colours:
            self._colourMap = ColourMap(colours)
        else:
            self._colourMap = self._defaultColourMap

        if properties and not isinstance(properties,dict):
            raise TypeError("'properties' object passed in must be of python type 'dict'")
        if not properties:
            self._properties = {}
        else:
            self._properties = properties

        if not isinstance(opacity,(int,float)):
            raise TypeError("'opacity' object passed in must be of python type 'int' or 'float'")
        if float(opacity) > 1. or float(opacity) < -1.:
            raise ValueError("'opacity' object must takes values from 0. to 1., while a value of -1 explicitly disables opacity.")
        self._opacity = opacity
        
        if not isinstance(colourBar, bool):
            raise TypeError("'colourBar' parameter must be of 'bool' type.")
        self._colourBar = None
        if colourBar:
            #Create the associated colour bar
            self._colourBar = ColourBar(colourMap=self._colourMap)
     
        # build parent
        super(Drawing,self).__init__()

    def _add_to_stg_dict(self,componentDictionary):
        
        # call parents method
        super(Drawing,self)._add_to_stg_dict(componentDictionary)

        # add an empty(ish) drawing object.  children should fill it out.
        componentDictionary[self._dr.name].update( {
            "properties"    :self._getProperties(),
            "ColourMap"     :self._colourMap._cm.name,
            "opacity"       :self.opacity
        } )

    def _getProperties(self):
        #Convert properties to string
        propstr = ''
        for key in self._properties:
            propstr += key + '=' + str(self._properties[key]) + '\n'
        return propstr

    def _updateProperties(self, newProps, overwrite=False):
        #Update the properties values, set overwrite to True to replace duplicates
        #with new values, default behaviour is to keep existing when merging
        if overwrite:
            self._properties.update(newProps)
        else:
            newProps.update({k:v for k,v in self._properties.iteritems() if v})
            self._properties = newProps

    @property
    def opacity(self):
        """    opacity (float): Opacity of drawing object.  Takes values from 0. to 1., while a value of -1 explicitly disables opacity.
        """
        return self._opacity

class ColourBar(Drawing):
    _selfObjectName = "_dr"
    _objectsDict = { "_dr": "lucDrawingObject" }

    def __init__(self, **kwargs):
        # build parent
        super(ColourBar,self).__init__(**kwargs)

        #Replace any missing properties with defaults, TODO: allow setting ColourBar props via args
        self._updateProperties({"colourbar" : 1, "height" : 10, "lengthfactor" : 0.8, 
                "margin" : 16, "border" : 1, "precision" : 2, "scientific" : False, "font" : "small", 
                "ticks" : 2 if self._colourMap.logScale else 0, "printticks" : True, "printunits" : False, "scalevalue" : 1.0}) #tick0-tick10 : val
    
    def _add_to_stg_dict(self,componentDictionary):

        # call parents method
        super(ColourBar,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name].update( {
        } )

class CrossSection(Drawing):
    """  This drawing object class defines a cross-section plane, derived classes plot data over this cross section
    """
    _objectsDict = { "_dr": "lucCrossSection" }

    def __init__(self, fn, mesh, crossSection="", **kwargs):
        self._fn = underworld.function.Function._CheckIsFnOrConvertOrThrow(fn)
        
        if not isinstance(mesh,uwmesh.FeMesh):
            raise TypeError("'mesh' object passed in must be of type 'FeMesh'")
        self._mesh = mesh

        if not isinstance(crossSection,str):
            raise ValueError("'crossSection' argument must be of python type 'str'")
        self._crossSection = crossSection

        # build parent
        super(CrossSection,self).__init__(**kwargs)

    def _setup(self):
        gLucifer._lucCrossSection_SetFn( self._cself, self._fn._fncself )

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        
        # call parents method
        super(CrossSection,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name].update( {
                   "Mesh": self._mesh._cself.name,
                   "crossSection": self._crossSection
            } )

    @property
    def crossSection(self):
        """    crossSection (str): Cross Section definition, eg;: z=0.
        """
        return self._crossSection

class Surface(CrossSection):
    """  This drawing object class draws a surface using the provided scalar field.
    """
    _objectsDict = { "_dr": None }

    def __new__(cls, drawSides="xyzXYZ", useMesh=False, *args, **kwargs):

        #Use the mesh sampler if requested
        if useMesh:
            cls._objectsDict = { "_dr": "lucScalarFieldOnMesh" }
        else:
            cls._objectsDict = { "_dr": "lucScalarField" }
        return super(Surface, cls).__new__(cls, *args, **kwargs)

    def __init__(self, drawSides="xyzXYZ", useMesh=False, *args, **kwargs):

        if not isinstance(drawSides,str):
            raise ValueError("'drawSides' argument must be of python type 'str'")
        self._drawSides = drawSides
        
        # build parent
        super(Surface,self).__init__(**kwargs)

        #Replace any missing properties with defaults
        self._updateProperties({"cullface" : True});
        # TODO: disable lighting if 2D (how to get dims?)
        #self._properties["lit"] = False;

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        # append random string to provided name to ensure unique component names
        # call parents method
        
        super(Surface,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name]["drawSides"] = self.drawSides
        componentDictionary[self._dr.name][     "Mesh"] = self._mesh._cself.name

    def _setup(self):
        gLucifer._lucCrossSection_SetFn( self._cself, self._fn._fncself )

    @property
    def drawSides(self):
        """    drawSides (str): sides (x,y,z,X,Y,Z) for which the surface should be drawn.  default is all sides ("xyzXYZ").
        """
        return self._drawSides

class Points(Drawing):
    """  This drawing object class draws a swarm of points.
    """
    _objectsDict = { "_dr": "lucSwarmViewer" }

    def __init__(self, swarm, fn_colour=None, fn_mask=None, pointSize=1.0, pointType=None, **kwargs):
        if not isinstance(swarm,swarmMod.Swarm):
            raise TypeError("'swarm' object passed in must be of type 'Swarm'")
        self._swarm = swarm

        self._fn_colour = None
        if fn_colour != None:
           self._fn_colour = underworld.function.Function._CheckIsFnOrConvertOrThrow(fn_colour)
        self._fn_mask = None
        if fn_mask != None:
           self._fn_mask = underworld.function.Function._CheckIsFnOrConvertOrThrow(fn_mask)

        if not isinstance(pointSize,(float,int)):
            raise TypeError("'pointSize' object passed in must be of python type 'float' or 'int'")

        if not isinstance(pointType,(int)):
            raise TypeError("'pointType' object passed in must be of python type 'int'")

        # build parent
        super(Points,self).__init__(**kwargs)

        #Replace any missing properties with defaults
        self._updateProperties({"pointsize" : pointSize, "pointtype" : pointType});

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        
        super(Points,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[ self._cself.name ][ "Swarm" ] = self.swarm._cself.name
        
    def _setup(self):
        fnc_ptr = None
        if self._fn_colour:
            fnc_ptr = self._fn_colour._fncself

        fnm_ptr = None
        if self._fn_mask:
            fnm_ptr = self._fn_mask._fncself

        gLucifer._lucSwarmViewer_SetFn( self._cself, fnc_ptr, fnm_ptr, None, None )


    @property
    def swarm(self):
        """    swarm (str): name of live underworld swarm for which points will be rendered.
        """
        return self._swarm
    @property
    def fn_colour(self):
        """    fn_colour (uw.Function): Function evaluated to determine particle colour.
        """
        return self._colourVariable
    @property
    def pointSize(self):
        """    pointSize (float): size of points
        """
        return self._properties["pointsize"]

    @property
    def pointType(self):
        """    pointType (int): points type [0-4]
        """
        return self._properties["pointType"]

class GridSampler3D(CrossSection):
    """  This drawing object class samples a regular grid in 3D.
    """
    _objectsDict = { "_dr": None } #Abstract class, Set by child

    def __init__(self, resolutionX=16, resolutionY=16, resolutionZ=16, **kwargs):
        if resolutionX:
            if not isinstance(resolutionX,(int)):
                raise TypeError("'resolutionX' object passed in must be of python type 'int'")
        if resolutionY:
            if not isinstance(resolutionY,(int)):
                raise TypeError("'resolutionY' object passed in must be of python type 'int'")
        if resolutionZ:
            if not isinstance(resolutionZ,(int)):
                raise TypeError("'resolutionZ' object passed in must be of python type 'int'")

        self._resolutionX = resolutionX
        self._resolutionY = resolutionY
        self._resolutionZ = resolutionZ

        # build parent
        super(GridSampler3D,self).__init__(**kwargs)

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        
        # call parents method
        super(GridSampler3D,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name].update( {
            "resolutionX": self.resolutionX,
            "resolutionY": self.resolutionY,
            "resolutionZ": self.resolutionZ
            } )

    @property
    def resolutionX(self):
        """    resolutionX (int): Number of samples in the X direction. Default is 16.
        """
        return self._resolutionX
    @property
    def resolutionY(self):
        """    resolutionY (int): Number of samples in the Y direction. Default is 16.
        """
        return self._resolutionY
    @property
    def resolutionZ(self):
        """    resolutionZ (int): Number of samples in the Z direction. Default is 16.
        """
        return self._resolutionZ

class VectorArrows(GridSampler3D):
    """  This drawing object class draws vector arrows corresponding to the provided vector field.
    """
    _objectsDict = { "_dr": "lucVectorArrows" }

    def __init__(self, arrowHead=0.3, scaling=0.3, glyphs=3, **kwargs):
        if arrowHead:
            if not isinstance(arrowHead,(float,int)):
                raise TypeError("'arrowHead' object passed in must be of python type 'int' or 'float'")
            if arrowHead < 0 or arrowHead > 1:
                raise ValueError("'arrowHead' can only take values between zero and one. Value provided is " + str(arrowHead)+".")
        if scaling:
            if not isinstance(scaling,(float,int)):
                raise TypeError("'scaling' object passed in must be of python type 'int' or 'float'")
        if glyphs:
            if not isinstance(glyphs,(int)):
                raise TypeError("'glyphs' object passed in must be of python type 'int'")

        # build parent
        super(VectorArrows,self).__init__(**kwargs)

        #Replace any missing properties with defaults
        self._updateProperties({"arrowHead" : arrowHead, "scaling" : scaling, "glyphs" : glyphs});

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        
        # call parents method
        super(VectorArrows,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name].update( {} )

    @property
    def arrowHead(self):
        """    arrowHead (float): The size of the head of the arrow compared with the arrow length. Must be between [0, 1].   Default is 0.3.
        """
        return self._properties["arrowhead"]
    @property
    def scaling(self):
        """    scaling (float): A factor to scale the size of the arrows by.  Default is 0.3.
        """
        return self._properties["scaling"]
    @property
    def glyphs(self):
        """    glyphs (int): Type of glyph to render for vector arrow. (0: Line, 1 or more: 3d arrow, higher number => better quality)
        """
        return self._properties["glyphs"]

class Volume(GridSampler3D):
    """  This drawing object class draws a volume using the provided scalar field.
    """
    _objectsDict = { "_dr": "lucFieldSampler" }

    def __init__(self, **kwargs):
        # build parent
        super(Volume,self).__init__(**kwargs)

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        
        # call parents method
        super(Volume,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name].update( {
            } )

class Mesh(Drawing):
    """  This drawing object class draws a mesh.
    """
    _objectsDict = { "_dr": "lucMeshViewer" }

    def __init__(self, mesh, nodeNumbers=False, segmentsPerEdge=1, *args, **kwargs):

        if not isinstance(mesh,uwmesh.FeMesh):
            raise TypeError("'mesh' object passed in must be of type 'FeMesh'")
        self._mesh = mesh

        if not isinstance(nodeNumbers,bool):
            raise TypeError("'nodeNumbers' flag must be of type 'bool'")
        self._nodeNumbers = nodeNumbers

        if not isinstance(segmentsPerEdge,int) or segmentsPerEdge < 1:
            raise TypeError("'segmentsPerEdge' must be a positive 'int'")
        self._segmentsPerEdge = segmentsPerEdge
        
        # build parent
        super(Mesh,self).__init__(**kwargs)

        #Replace any missing properties with defaults
        self._updateProperties({"lit" : False, "linewidth" : 0.1, 
                                "pointsize" : 5 if self._nodeNumbers else 1, 
                                "pointtype" : 2 if self._nodeNumbers else 4});

    def _add_to_stg_dict(self,componentDictionary):
        # lets build up component dictionary
        # append random string to provided name to ensure unique component names
        # call parents method
        
        super(Mesh,self)._add_to_stg_dict(componentDictionary)

        componentDictionary[self._dr.name][       "Mesh"] = self._mesh._cself.name
        componentDictionary[self._dr.name]["nodeNumbers"] = self._nodeNumbers
        componentDictionary[self._dr.name][   "segments"] = self._segmentsPerEdge
