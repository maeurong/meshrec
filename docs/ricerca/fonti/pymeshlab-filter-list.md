Here are listed all the filter names that can be given as a parameter to the function [`pmeshlab.MeshSet.apply_filter()`](https://pymeshlab.readthedocs.io/en/latest/classes/meshset.html#pmeshlab.MeshSet.apply_filter "pmeshlab.MeshSet.apply_filter").

Each filter accepts a list of parameters, that can be semantically classified as follows:

> - Boolean: a classic `bool` value;
> - Integer: a classic `int` value;
> - String: a classic `str` value;
> - Float: a classic `float` value;
> - Bounded Float: a classic `float` that is expected to be bounded between a `min` and a `max` value; an out-of-bounds value will be clamped in \[min-max\];
> - PercentageValue: represents a parameter that is relative to some other measure, specified in the documentation of the filter. This parameter can be of two different types:
> 	- [`pmeshlab.PercentageValue`](https://pymeshlab.readthedocs.io/en/latest/classes/percentage_value.html#pmeshlab.PercentageValue "pmeshlab.PercentageValue") (recommended): the parameter will be treated as relative percentage value; see the documentation of the [`pmeshlab.PercentageValue`](https://pymeshlab.readthedocs.io/en/latest/classes/percentage_value.html#pmeshlab.PercentageValue "pmeshlab.PercentageValue") for further info;
> 		- [`pmeshlab.PureValue`](https://pymeshlab.readthedocs.io/en/latest/classes/pure_value.html#pmeshlab.PureValue "pmeshlab.PureValue"): the parameter will be treated as a pure value; see the documentation of the [`pmeshlab.PureValue`](https://pymeshlab.readthedocs.io/en/latest/classes/pure_value.html#pmeshlab.PureValue "pmeshlab.PureValue") for further info;
> - Enum: represents a parameter that can accept just one of a limited set of possible values. These values type can be `int` or `str`; see the documentation of the specific filter for further info;
> - Color: represents a color, and the parameter can be of type [`pmeshlab.Color`](https://pymeshlab.readthedocs.io/en/latest/classes/color.html#pmeshlab.Color "pmeshlab.Color"); see the documentation of the [`pmeshlab.Color`](https://pymeshlab.readthedocs.io/en/latest/classes/color.html#pmeshlab.Color "pmeshlab.Color") for further info;
> - 3D Point (or 3D Vector): represents a 3D point or vector, and the parameter can be of type `numpy.ndarray[numpy.float64[3]]` (a numpy array containing three floats);
> - 4x4 Matrix: represents a 4x4 Matrix of floats, and the parameter can be of type `numpy.ndarray[numpy.float64[4, 4]]` (a 4x4 numpy array of floats);
> - Mesh: represents a parameter that links to one of the meshes contained in the MeshSet on which the filter is applied. This parameter is of type `int`, which indicates the `id` of the mesh in the MeshSet;
> - File Name: a classic `str` that represents the path of a file that is going to be saved or loaded by the filter. The string is expected to have at least an extension on its final characters; see the documentation of the specific filter for further info;
> - Camera: *still not supported*;

The [`pmeshlab.MeshSet.apply_filter()`](https://pymeshlab.readthedocs.io/en/latest/classes/meshset.html#pmeshlab.MeshSet.apply_filter "pmeshlab.MeshSet.apply_filter") returns a dictionary that may contain some values returned by the applied filter. Most of the filters do not return nothing, therefore the dictionary will be empty.

**Please note**: some filter parameters depend on the mesh(es) used as input of the filter. Default values listed here are computed on a 1x1x1 cube (pymeshlab/tests/sample/cube.obj), but their value will be computed on the input mesh if they are left as default.

## Filter documentation

apply\_cameras\_extrinsics\_transformation [](#apply_cameras_extrinsics_transformation "Link to this definition")

*MeshLab filter name*: ‘Transform the camera extrinsics, or all the cameras of the project’

Transform the camera extrinsics, or all the cameras of the project.

**Parameters:**

`transformmatrix : numpy.ndarray[numpy.float64[4, 4]] = [[1, 0, 0, 0],[0, 1, 0, 0],[0, 0, 1, 0],[0, 0, 0, 1]]`

> :

`camera : str = 'Raster Camera' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Raster Camera'`
> > 1. `'Mesh Camera'`
> 
> *Camera type*: Choose the camera to scale

`behaviour : str = 'The matrix is the transformation to apply to the extrinsics' (or int = 0)`

> Possible enum values:
> 
> > 0. `'The matrix is the transformation to apply to the extrinsics'`
> > 1. `'The matrix represent the new extrinsics'`
> 
> *Matrix semantic*: What the matrix is used for

`toallraster : bool = False`

> *Apply to all active Raster layers*: Apply the same scaling to all the active Raster layers: it is taken into account only if 'Raster Camera' is selected

`toall : bool = False`

> *Apply to all active Raster and visible Mesh layers*: Apply the same scaling to all the layers, including any visible 3D layer

apply\_cameras\_rotation [](#apply_cameras_rotation "Link to this definition")

*MeshLab filter name*: ‘Transform: Rotate Camera or set of cameras’

Rotate the camera, or all the cameras of the project. The selected raster is the reference if viewpoint rotation is selected.

**Parameters:**

`camera : str = 'Raster Camera' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Raster Camera'`
> > 1. `'Mesh Camera'`
> 
> *Camera type*: Choose the camera to scale

`rotaxis : str = 'X axis' (or int = 0)`

> Possible enum values:
> 
> > 0. `'X axis'`
> > 1. `'Y axis'`
> > 2. `'Z axis'`
> > 3. `'custom axis'`
> 
> *Rotation on:*: Choose a method

`rotcenter : str = 'origin' (or int = 0)`

> Possible enum values:
> 
> > 0. `'origin'`
> > 1. `'camera viewpoint'`
> > 2. `'custom point'`
> 
> *Center of rotation:*: Choose a method

`angle : float (bounded) = 0 [min: -360; max: 360]`

> *Rotation Angle*: Angle of rotation (in **degree**). If snapping is enabled this value is rounded according to the snap value

`customaxis : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom axis*: This rotation axis is used only if the 'custom axis' option is chosen.

`customcenter : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom center*: This rotation center is used only if the 'custom point' option is chosen.

`toallraster : bool = False`

> *Apply to all active Raster layers*: Apply the same scaling to all the active Raster layers: it is taken into account only if 'Raster Camera' is selected

`toall : bool = False`

> *Apply to all active Raster and visible Mesh layers*: Apply the same scaling to all the layers, including any visible 3D layer

apply\_cameras\_scaling [](#apply_cameras_scaling "Link to this definition")

*MeshLab filter name*: ‘Transform: Scale Camera or set of cameras’

Scale the camera, or all the cameras of the project. The selected raster is the reference if viewpoint scaling is selected.

**Parameters:**

`camera : str = 'Raster Camera' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Raster Camera'`
> > 1. `'Mesh Camera'`
> 
> *Camera type*: Choose the camera to scale

`scalecenter : str = 'origin' (or int = 0)`

> Possible enum values:
> 
> > 0. `'origin'`
> > 1. `'camera viewpoint'`
> > 2. `'custom point'`
> 
> *Center of scaling:*: Choose a method

`customcenter : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom center*: This scaling center is used only if the 'custom point' option is chosen.

`scale : float = 1`

> *Scale factor*: The scale factor that has to be applied to the camera

`toallraster : bool = False`

> *Apply to all active Raster layers*: Apply the same scaling to all the active Raster layers: it is taken into account only if 'Raster Camera' is selected

`toall : bool = False`

> *Apply to all active Raster and visible Mesh layers*: Apply the same scaling to all the layers, including any visible 3D layer

apply\_cameras\_translation [](#apply_cameras_translation "Link to this definition")

*MeshLab filter name*: ‘Transform: Translate Camera or set of cameras’

Translate the camera, or all the cameras of the project.

**Parameters:**

`camera : str = 'Raster Camera' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Raster Camera'`
> > 1. `'Mesh Camera'`
> 
> *Camera type*: Choose the camera to scale

`axisx : float (bounded) = 0 [min: -1000; max: 1000]`

> *X Axis*: Absolute translation amount along the X axis

`axisy : float (bounded) = 0 [min: -1000; max: 1000]`

> *Y Axis*: Absolute translation amount along the Y axis

`axisz : float (bounded) = 0 [min: -1000; max: 1000]`

> *Z Axis*: Absolute translation amount along the Z axis

`centerflag : bool = False`

> *translate viewpoint position to the origin*: If selected, the camera viewpoint is translated to the origin

`toallraster : bool = False`

> *Apply to all active Raster layers*: Apply the same scaling to all the active Raster layers: it is taken into account only if 'Raster Camera' is selected

`toall : bool = False`

> *Apply to all active Raster and Mesh layers*: Apply the same scaling to all the layers, including any visible 3D layer

apply\_color\_brightness\_contrast\_gamma\_per\_vertex [](#apply_color_brightness_contrast_gamma_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Brightness Contrast Gamma’

Change the color the vertices of the mesh adjusting brightness, contrast and gamma.

**Parameters:**

`brightness : float (bounded) = 0 [min: -255; max: 255]`

> *Brightness:*: Sets the amount of brightness that will be added/subtracted to the colors.  
> Brightness = 255 -> all white;  
> Brightness = -255 -> all black;

`contrast : float (bounded) = 0 [min: -255; max: 255]`

> *Contrast factor:*: Sets the amount of contrast of the mesh.

`gamma : float (bounded) = 1 [min: 0.1; max: 5]`

> *Gamma:*: Sets the values of the exponent gamma.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_desaturation\_per\_vertex [](#apply_color_desaturation_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Desaturation’

The filter desaturates the colors of the mesh. This provides a simple way to convert a mesh in gray tones. The user can choose the desaturation method to apply; they are based on Lightness, Luminosity and Average.

**Parameters:**

`method : str = 'Lightness' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Lightness'`
> > 1. `'Luminosity'`
> > 2. `'Average'`
> 
> *Desaturation method:*: Lightness is computed as (Max(r,g,b)+Min(r,g,b))/2  
> Luminosity is computed as 0.212\*r + 0.715\*g + 0.072\*b  
> Average is computed as (r+g+b)/3

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_equalization\_per\_vertex [](#apply_color_equalization_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Equalize Vertex Color’

The filter equalizes the colors histogram. It is a kind of automatic regulation of contrast; the colors histogram is expanded to fit all the range of colors.

**Parameters:**

`rch : bool = True`

> *Red Channel:*: Select the red channel.

`gch : bool = True`

> *Green Channel:*: Select the green channel.

`bch : bool = True`

> *Blue Channel:*: Select the blue channel.  
>   
> If no channel is selected  
> filter works on Lightness.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_intensity\_colourisation\_per\_vertex [](#apply_color_intensity_colourisation_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Colourisation’

Allows the application of a color to the mesh. In spite of the Fill operation, the color is blended with the mesh according to a given intensity.

**Parameters:**

`hue : float (bounded) = 0 [min: 0; max: 360]`

> *Hue:*: Changes the hue of the mesh.

`saturation : float (bounded) = 100 [min: 0; max: 100]`

> *Saturation:*: Changes the saturation of the mesh.

`luminance : float (bounded) = 50 [min: 0; max: 100]`

> *Luminance:*: Changes the luminance of the mesh.

`intensity : float (bounded) = 50 [min: 0; max: 100]`

> *Blending:*: Sets the blending factor used in adding the new color to the existing one.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_inverse\_per\_vertex [](#apply_color_inverse_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Invert’

Inverts the colors of the vertices of the mesh.

**Parameters:**

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_laplacian\_smoothing\_per\_face [](#apply_color_laplacian_smoothing_per_face "Link to this definition")

*MeshLab filter name*: ‘Smooth: Laplacian Face Color’

Laplacian Smooth Face Color

**Parameters:**

`iteration : int = 1`

> *Iteration*: the number of iteration of the smoothing algorithm

apply\_color\_laplacian\_smoothing\_per\_vertex [](#apply_color_laplacian_smoothing_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Smooth: Laplacian Vertex Color’

Laplacian Smooth Vertex Color

**Parameters:**

`iteration : int = 1`

> *Iteration*: the number of iteration of the smoothing algorithm

apply\_color\_level\_adjustment\_per\_vertex [](#apply_color_level_adjustment_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Levels Adjustment’

The filter allows adjustment of color levels. It is a custom way to map an interval of color into another one. The user can set the input minimum and maximum levels, gamma and the output minimum and maximum levels (many tools call them respectively input black point, white point, gray point, output black point and white point).

**Parameters:**

`gamma : float (bounded) = 1 [min: 0.1; max: 5]`

> *Gamma:*:

`in_min : float (bounded) = 0 [min: 0; max: 255]`

> *Min input level:*:

`in_max : float (bounded) = 255 [min: 0; max: 255]`

> *Max input level:*:

`out_min : float (bounded) = 0 [min: 0; max: 255]`

> *Min output level:*:

`out_max : float (bounded) = 255 [min: 0; max: 255]`

> *Max output level:*:

`rch : bool = True`

> *Red Channel:*:

`gch : bool = True`

> *Green Channel:*:

`bch : bool = True`

> *Blue Channel:*:

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

`apply_to_all : bool = False`

> *All visible layers*: if true, apply to all visible layers

apply\_color\_noising\_per\_vertex [](#apply_color_noising_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Color noise’

Adds to the color the requested amount of bits of noise. Bits of noise are added independently for each RGB channel.

**Parameters:**

`noisebits : int = 1`

> *Noise bits:*: Bits of noise added to each RGB channel. Example: 3 noise bits adds three random offsets in the \[-4,+4\] interval to each RGB channels.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_thresholding\_per\_vertex [](#apply_color_thresholding_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Thresholding’

Colors the vertices of the mesh using two colors according to a lightness threshold (on the original color).

**Parameters:**

`color1 : Color = [0; 0; 0; 255]`

> *Color 1:*: Sets the color to apply below the threshold.

`color2 : Color = [255; 255; 255; 255]`

> *Color 2:*: Sets the color to apply above the threshold.

`threshold : float (bounded) = 128 [min: 0; max: 255]`

> *Threshold:*: Vertices with color above the lightness threshold becomes Color 2, the others Color 1.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_color\_unsharp\_mask\_per\_vertex [](#apply_color_unsharp_mask_per_vertex "Link to this definition")

*MeshLab filter name*: ‘UnSharp Mask Color’

Apply Unsharp filter to the vertex color, putting in more evidence color variations.  
See [Unsharp Masking](https://en.wikipedia.org/wiki/Unsharp_masking)

**Parameters:**

`weight : float = 0.3`

> *Unsharp Weight*: the unsharp weight *w <sub><big>u</big></sub>* in the unsharp mask equation:  
> *w <sub><big>o</big></sub> orig + w <sub><big>u</big></sub> (orig - lowpass)*

`weightorig : float = 1`

> *Original Color Weight*: How much the original signal is used, e.g. the weight *w <sub><big>o</big></sub>* in the above unsharp mask equation  
> Usually you should not need to change the default 1.0 value.

`iterations : int = 5`

> *Smooth Iterations*: number of iterations of laplacian smooth in every run

apply\_color\_white\_balance\_per\_vertex [](#apply_color_white_balance_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color White Balance’

The filter provides a standard white balance transformation. It is done correcting the RGB channels with a factor such that, the brighter color in the mesh, that is supposed to be white, becomes really white.

**Parameters:**

`color : Color = [255; 255; 255; 255]`

> *Unbalanced white:* : The color that is supposed to be white.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

apply\_coord\_craters\_from\_point\_cloud [](#apply_coord_craters_from_point_cloud "Link to this definition")

*MeshLab filter name*: ‘Craters Generation’

Generates craters onto a mesh using radial functions.  
There must be at least two layers to apply this filter:  
- the layer that contains the target mesh; we assume that this mesh is sufficiently refined;
- the layer that contains the samples which represent the central points of craters.
There are three radial functions available to generate craters, two of which are Gaussian and Multiquadric, and the third is a variant of multiquadric. Blending functions are also provided to blend the crater elevation towards the mesh surface. If you want the preview to work, be sure to select the target mesh layer before launching the filter. You can select this layer by clicking on it in the layer dialog.

**Parameters:**

`target_mesh : int = 0`

> *Target mesh:*: The mesh on which craters will be generated.

`samples_mesh : int = 0`

> *Samples layer:*: The samples that represent the central points of craters.

`seed : int = 0`

> *Seed:*: The seed with which the random number generator is initialized. The random generator generates radius and depth for each crater into the given range.

`smoothingsteps : int = 5`

> *Normals smoothing steps:*: Vertex normals are smoothed this number of times before generating craters.

`rbf : str = 'f2 (Multiquadric)' (or int = 1)`

> Possible enum values:
> 
> > 0. `'f1 (Gaussian)'`
> > 1. `'f2 (Multiquadric)'`
> > 2. `'f3'`
> 
> *Radial function:*: The radial function used to generate craters.

`min_radius : float (bounded) = 0.1 [min: 0; max: 1]`

> *Min crater radius:*: Defines the minimum radius of craters in range \[0, 1\]. Values near 0 mean very small craters.

`max_radius : float (bounded) = 0.35 [min: 0; max: 1]`

> *Max crater radius:*: Defines the maximum radius of craters in range \[0, 1\]. Values near 1 mean very large craters.

`min_depth : float (bounded) = 0.05 [min: 0; max: 1]`

> *Min crater depth:*: Defines the minimum depth of craters in range \[0, 1\].

`max_depth : float (bounded) = 0.15 [min: 0; max: 1]`

> *Max crater depth:*: Defines the maximum depth of craters in range \[0, 1\]. Values near 1 mean very deep craters.

`elevation : float (bounded) = 0.4 [min: 0; max: 1]`

> *Elevation:*: Defines how much the crater rise itself from the mesh surface, giving an "impact-effect".

`blend : str = 'f3 blending' (or int = 3)`

> Possible enum values:
> 
> > 0. `'Exponential blending'`
> > 1. `'Linear blending'`
> > 2. `'Gaussian blending'`
> > 3. `'f3 blending'`
> 
> *Blending algorithm:*: The algorithm that is used to blend the perturbation towards the mesh surface.

`blendthreshold : float (bounded) = 0.8 [min: 0; max: 1]`

> *Blending threshold:*: The fraction of craters radius beyond which the radial function is replaced with the blending function.

`successiveimpacts : bool = True`

> *Successive impacts*: If not checked, the impact-effects of generated craters will be superimposed with each other.

`ppnoise : bool = True`

> *Postprocessing noise*: Slightly perturbates the craters with a noise function.

`invert : bool = False`

> *Invert perturbation*: If checked, inverts the sign of radial perturbation to create bumps instead of craters.

`save_as_quality : bool = False`

> *Save as vertex quality*: Saves the perturbation as vertex quality.

apply\_coord\_cubic\_stylization [](#apply_coord_cubic_stylization "Link to this definition")

*MeshLab filter name*: ‘Cubic stylization’

Turn a mesh into a cube's style maintaining its original shape.  
For all detailed about cubic stylization see:  
  
*Hsueh-Ti Derek Liu and Alec Jacobson.*  
**Cubic Stylization** ([pdf](https://www.dgp.toronto.edu/projects/cubic-stylization/cubicStyle_high.pdf))  
in ACM Transactions on Graphics, 2019  
  

**Parameters:**

`lcubeness : float = 0.2`

> *Cubeness parameter (λ)*: Control the cubeness of the mesh. Generally, the higher the cubeness parameter, the more cubic the mesh is. λ ∈ \[0, 1\]

`applyef : bool = False`

> *Apply edge flipping*: Apply edge flip optimization on cubic stylization.

`applycol : bool = False`

> *Colorize by vertex Quality*: Color vertices depending on their cubization energy.

apply\_coord\_depth\_smoothing [](#apply_coord_depth_smoothing "Link to this definition")

*MeshLab filter name*: ‘Depth Smooth’

A laplacian smooth that is constrained to move vertices only in one given direction (usually the viewer direction).

**Parameters:**

`stepsmoothnum : int = 3`

> *Smoothing steps*: The number of times that the whole algorithm (normal smoothing + vertex fitting) is iterated.

`viewpoint : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Viewpoint*: The position of the view point that is used to get the constraint direction.

`delta : PercentageValue = 100%`

> *Strength*: How much smoothing is applied: 0 (no smooth) e 1 (full smooth)

`selected : bool = False`

> *Affect only selection*: If checked the filter is performed only on the selected area

apply\_coord\_developability\_of\_mesh [](#apply_coord_developability_of_mesh "Link to this definition")

*MeshLab filter name*: ‘Make mesh developable’

The filter improves the developability of the current two-manifold triangular mesh by applying an optimization process that encourages each vertex star to form an hinge or a flat piece. The resulting mesh is similar to the initial, but it is comprised of one or more developable pieces held toghether by highly regular seam curves, i.e. path of edges which vertex stars did not form an hinge or a flat spot.  
Since small interior angles can have a negative impact on the outcome, an automatic remeshing that runs along the optimization can be enabled.  
When the obtained design is satisfactory, one may want to refine the quality of the seams and the developability of the surfaces by alternating between regular midpoint subdivisions and further optimization rounds.  
For more details see:  
**Oded Stein, Eitan Grinspun and Keenan Crane**  
['Developability of triangle meshes'](https://doi.org/10.1145/3197517.3201303)  
ACM Transactions on Graphics, Volume 37, Issue 4

**Parameters:**

`optmethod : str = '[B] Backtracking line search' (or int = 1)`

> Possible enum values:
> 
> > 0. `'[F] Fixed stepsize'`
> > 1. `'[B] Backtracking line search'`
> 
> *Gradient method*: The gradient method optimization algorithm to use

`maxfunevals : int = 400`

> *Max function evaluations*: The maximum number of function evaluation. Once reached, the optimization stops

`eps : float = 1e-05`

> *Stop threshold*: Optimization stops when the squared norm of the gradient is less than or equal to the accuracy

`stepsize : float = 0.01`

> *Initial step size*: The initial step size of the opt method, fixed when using \[F\] optimizer

`minstepsize : float = 1e-10`

> *Min step size (B only)*: The minimum step size for the backtracking line search opt method

`tau : float = 0.8`

> *Tau (B only)*: Scaling factor of the step size for the backtracking line search opt method

`m1 : float = 0.0001`

> *Armijo constant (B only)*: The constant of the Armijo condition of the backtracking line search opt method

`edgeflips : bool = True`

> *Apply edge flips*: Whether or not to apply edge flips when necessary during optimization

`edgecollapses : bool = True`

> *Apply edge collapses*: Whether or not to apply edge collapses when necessary during optimization

`anglethreshold : float = 18`

> *Post-processing angle threshold (deg)*: The maximum angle under which an edge flip or an edge collapse must be performed during optimization

apply\_coord\_directional\_preservation [](#apply_coord_directional_preservation "Link to this definition")

*MeshLab filter name*: ‘Directional Geometry Preservation’

Blend through a given direction the geometry previously stored in a per vertex custom point attribute with the current geometry. This is useful to limit the influence of any smoothing algorithm along the viewing direction. This is useful to cope with the biased distribution of measuring error in many scanning devices, because TOF scanners usually have very good *x,y* accuracy but suffer of greater depth errors.

**Parameters:**

`attr_name : str = ''`

> *Custom attribute name*: The name of the per vertex custom point attribute that contains the previous geometry.

`viewpoint : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Viewpoint*: The position of the view point that is used to get the constraint direction.

apply\_coord\_fractal\_displacement [](#apply_coord_fractal_displacement "Link to this definition")

*MeshLab filter name*: ‘Fractal Displacement’

Generates a fractal terrain perturbation with five different algorithms.  
Some good parameter values to start with are:  

| \- | Seed | Octaves | Lacunarity | Fractal increment | Offset | Gain |
| --- | --- | --- | --- | --- | --- | --- |
| fBM | 1 | 10 | 2 | 1.2 | \- | \- |
| Standard multifractal | 1 | 8 | 2 | 0.9 | 0.9 | \- |
| Heterogeneous multifractal | 1 | 8 | 3 | 0.9 | 0.4 | \- |
| Hybrid multifractal | 1 | 8 | 4 | 0.1 | 0.3 | \- |
| Ridged multifractal | 2 | 8 | 4 | 0.5 | 0.9 | 2 |

  
  
Detailed algorithms descriptions can be found in:  
*Ebert, D.S., Musgrave, F.K., Peachey, D., Perlin, K., and Worley, S.*  
**Texturing and Modeling: A Procedural Approach**  
Morgan Kaufmann Publishers Inc., San Francisco, CA, USA, 2002.  
  
Hint: search a good compromise between offset and height factor parameter.

**Parameters:**

`maxheight : PercentageValue = 4%`

> *Max height:*: Defines the maximum height for the perturbation.

`scale : float (bounded) = 1 [min: 0; max: 10]`

> *Scale factor:*: Scales the fractal perturbation in and out. Values larger than 1 mean zoom out; values smaller than one mean zoom in.

`smoothingsteps : int = 5`

> *Normals smoothing steps:*: Face normals will be smoothed to make the perturbation more homogeneous. This parameter represents the number of smoothing steps.

`seed : float = 2`

> *Seed:*: By varying this seed, the terrain morphology will change.  
> Don't change the seed if you want to refine the current terrain morphology by changing the other parameters.

`algorithm : str = 'Ridged multifractal terrain' (or int = 4)`

> Possible enum values:
> 
> > 0. `'fBM (fractal Brownian Motion)'`
> > 1. `'Standard multifractal'`
> > 2. `'Heterogeneous multifractal'`
> > 3. `'Hybrid multifractal terrain'`
> > 4. `'Ridged multifractal terrain'`
> 
> *Algorithm*: The algorithm with which the fractal terrain will be generated.

`octaves : float (bounded) = 8 [min: 1; max: 20]`

> *Octaves:*: The number of Perlin noise frequencies that will be used to generate the terrain. Reasonable values are in range \[2,9\].

`lacunarity : float = 4`

> *Lacunarity:*: The gap between noise frequencies. This parameter is used in conjunction with fractal increment to compute the spectral weights that contribute to the noise in each octave.

`fractalincrement : float = 0.2`

> *Fractal increment:*: This parameter defines how rough the generated terrain will be. The range of reasonable values changes according to the used algorithm, however you can choose it in range \[0.2, 1.5\].

`offset : float = 0.9`

> *Offset:*: This parameter controls the multifractality of the generated terrain. If offset is low, then the terrain will be smooth.

`gain : float = 2.5`

> *Gain:*: Ignored in all the algorithms except the ridged one. This parameter defines how hard the terrain will be.

`saveasquality : bool = False`

> *Save as vertex quality*: Saves the perturbation value as vertex quality.

apply\_coord\_hc\_laplacian\_smoothing [](#apply_coord_hc_laplacian_smoothing "Link to this definition")

*MeshLab filter name*: ‘HC Laplacian Smooth’

HC Laplacian Smoothing. Extended version of Laplacian Smoothing based on the article:  
**Improved Laplacian Smoothing of Noisy Surface Meshes** by *Vollmer, Mencl and Müller*. EUROGRAPHICS Volume 18 (1999), Number 3, 131-138.  
[doi:10.1111/1467-8659.00334](https://doi.org/10.1111/1467-8659.00334)

apply\_coord\_laplacian\_smoothing [](#apply_coord_laplacian_smoothing "Link to this definition")

*MeshLab filter name*: ‘Laplacian Smooth’

Laplacian smooth. Average each vertex position with weighted positions of neighbour vertices.  
**Laplacian Mesh Processing** by *Olga Sorkine*. EUROGRAPHICS 2005  
[doi:10.2312/egst.20051044](http://dx.doi.org/10.2312/egst.20051044)

**Parameters:**

`stepsmoothnum : int = 3`

> *Smoothing steps*: The number of times that the whole algorithm (normal smoothing + vertex fitting) is iterated.

`boundary : bool = True`

> *1D Boundary Smoothing*: Smooth boundary edges only by themselves (e.g. the polyline forming the boundary of the mesh is independently smoothed). This can reduce the shrinking on the border but can have strange effects on very small boundaries.

`cotangentweight : bool = True`

> *Cotangent weighting*: Use cotangent weighting scheme for the averaging of the position. Otherwise the simpler umbrella scheme (1 if the edge is present) is used.

`selected : bool = False`

> *Affect only selection*: If checked the filter is performed only on the selected area

apply\_coord\_laplacian\_smoothing\_scale\_dependent [](#apply_coord_laplacian_smoothing_scale_dependent "Link to this definition")

*MeshLab filter name*: ‘ScaleDependent Laplacian Smooth’

Scale Dependent Laplacian Smoothing, extended version of Laplacian Smoothing based on the Fujiwara extended umbrella operator.  
**Implicit Fairing of Irregular Meshes using Diffusion and Curvature Flow** by *Desbrun, Meyer, Schroeder and Barr*. SIGGRAPH 1999  
[doi:10.1145/311535.311576](https://doi.org/10.1145/311535.311576)

**Parameters:**

`stepsmoothnum : int = 3`

> *Smoothing steps*: The number of times that the whole algorithm (normal smoothing + vertex fitting) is iterated.

`delta : PercentageValue = 1%`

> *delta*:

`selected : bool = False`

> *Affect only selected faces*: If checked the filter is performed only on the selected faces

apply\_coord\_laplacian\_smoothing\_surface\_preserving [](#apply_coord_laplacian_smoothing_surface_preserving "Link to this definition")

*MeshLab filter name*: ‘Laplacian Smooth (surface preserving)’

Laplacian smooth with limited surface modification: move each vertex in the average position of neighbors vertices, only if the new position still (almost) lies on original surface

**Parameters:**

`selection : bool = False`

> *Update selection*: Apply laplacian smooth on selected faces only

`angledeg : float = 0.5`

> *Max Normal Dev (deg)*: maximum mean normal angle displacement (degrees) from old to new faces

`iterations : int = 1`

> *Iterations*: number of laplacian smooth iterations in every run

apply\_coord\_point\_cloud\_movement\_over\_mesh [](#apply_coord_point_cloud_movement_over_mesh "Link to this definition")

*MeshLab filter name*: ‘Points Cloud Movement’

Simulate the movement of a point cloud over a mesh

**Parameters:**

`point_cloud : int = 0`

> *Point cloud*: The point cloud that will be moved over the target mesh.

`target_mesh : int = 0`

> *Target mesh*: Target mesh on which the point cloud will be moved.

`gravity_dir : numpy.ndarray[numpy.float64[3]] = [0, -1, 0]`

> *g*: Direction of gravity

`force_dir : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *force*: Direction of the force acting on the points cloud

`steps : int = 1`

> *s*: Simulation Steps

`adhesion : float (bounded) = 1 [min: 0; max: 1]`

> *adhesion*: Factor to model the general adhesion.

`velocity : float = 0`

> *v*: Initial velocity of the particle

`mass : float = 1`

> *m*: Mass of the particle

`colorize_mesh : bool = False`

> *Map to Color*: Color the mesh with colors based on the movement of the particle

apply\_coord\_random\_displacement [](#apply_coord_random_displacement "Link to this definition")

*MeshLab filter name*: ‘Random Vertex Displacement’

Move the vertices of the mesh of a random quantity.

**Parameters:**

`updatenormals : bool = True`

> *Recompute normals*: Toggle the recomputation of the normals after the random displacement.  
>   
> If disabled the face normals will remains unchanged resulting in a visually pleasant effect.

`displacement : PercentageValue = 1%`

> *Max displacement*: The vertex are displaced of a vector whose norm is bounded by this value

`randomseed : int = 0`

> *Random Seed*: The seed used to generate random values. If seed is zero no random seed is used

apply\_coord\_taubin\_smoothing [](#apply_coord_taubin_smoothing "Link to this definition")

*MeshLab filter name*: ‘Taubin Smooth’

The λ-μ Taubin smoothing, combines two steps of low-pass filtering for each iteration. Based on the article:  
**A signal processing approach to fair surface design** by *Gabriel Taubin*, SIGGRAPH 1995  
[doi:10.1145/218380.218473](https://doi.org/10.1145/218380.218473)

**Parameters:**

`lambda_ : float = 0.5`

> *Lambda*: The lambda parameter of the Taubin Smoothing algorithm

`mu : float = -0.53`

> *mu*: The mu parameter of the Taubin Smoothing algorithm

`stepsmoothnum : int = 10`

> *Smoothing steps*: The number of times that the taubin smoothing is iterated. Usually it requires a larger number of iteration than the classical laplacian

`selected : bool = False`

> *Affect only selected faces*: If checked the filter is performed only on the selected faces

apply\_coord\_two\_steps\_smoothing [](#apply_coord_two_steps_smoothing "Link to this definition")

*MeshLab filter name*: ‘TwoStep Smooth’

Two Steps Smoothing, a feature preserving/enhancing fairing filter based on two stages:
1. Normal Smoothing, where similar normals are averaged together.
2. Vertex reposition, where vertices are moved to fit on the new normals.
**A Comparison of Mesh Smoothing Methods** by *A. Belyaev and Y. Ohtake*. Proc. Israel-Korea Bi-National Conf. Geometric Modeling and Computer Graphics, pp. 83-87, 2003.  
[publication](https://www.researchgate.net/publication/47861030_A_comparison_of_mesh_smoothing_methods)

**Parameters:**

`stepsmoothnum : int = 3`

> *Smoothing steps*: The number of times that the whole algorithm (normal smoothing + vertex fitting) is iterated.

`normalthr : float = 60`

> *Feature Angle Threshold (deg)*: Specify a threshold angle (0..90) for features that you want to be preserved.  
> Features forming angles LARGER than the specified threshold will be preserved.  
> 0 -> no smoothing  
> 90 -> all faces will be smoothed

`stepnormalnum : int = 20`

> *Normal Smoothing steps*: Number of iterations of normal smoothing step. The larger the better and (the slower)

`stepfitnum : int = 20`

> *Vertex Fitting steps*: Number of iterations of the vertex fitting procedure.

`selected : bool = False`

> *Affect only selected faces*: If checked the filter is performed only on the selected faces

apply\_coord\_unsharp\_mask [](#apply_coord_unsharp_mask "Link to this definition")

*MeshLab filter name*: ‘UnSharp Mask Geometry’

Apply Unsharp filter to geometric shape, putting in more evidence ridges and valleys variations.  
[Unsharp Masking](https://en.wikipedia.org/wiki/Unsharp_masking)

**Parameters:**

`weight : float = 0.3`

> *Unsharp Weight*: the unsharp weight *w <sub><big>u</big></sub>* in the unsharp mask equation:  
> *w <sub><big>o</big></sub> orig + w <sub><big>u</big></sub> (orig - lowpass)*

`weightorig : float = 1`

> *Original Weight*: How much the original signal is used, e.g. the weight *w <sub><big>o</big></sub>* in the above unsharp mask equation  
> Usually you should not need to change the default 1.0 value.

`iterations : int = 5`

> *Smooth Iterations*: number of iterations of laplacian smooth in every run

apply\_matrix\_flip\_or\_swap\_axis [](#apply_matrix_flip_or_swap_axis "Link to this definition")

*MeshLab filter name*: ‘Transform: Flip and/or swap axis’

Generate a matrix transformation that flips each one of the axis or swaps a couple of axis. The listed transformations are applied in that order. This kind of transformation cannot be applied to set of Raster!

**Parameters:**

`flipx : bool = False`

> *Flip X axis*: If selected the axis will be swapped (mesh mirrored along the YZ plane

`flipy : bool = False`

> *Flip Y axis*: If selected the axis will be swapped (mesh mirrored along the XZ plane

`flipz : bool = False`

> *Flip Z axis*: If selected the axis will be swapped (mesh mirrored along the XY plane

`swapxy : bool = False`

> *Swap X-Y axis*: If selected the two axis will be swapped. All the swaps are performed in this order

`swapxz : bool = False`

> *Swap X-Z axis*: If selected the two axis will be swapped. All the swaps are performed in this order

`swapyz : bool = False`

> *Swap Y-Z axis*: If selected the two axis will be swapped. All the swaps are performed in this order

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

apply\_matrix\_freeze [](#apply_matrix_freeze "Link to this definition")

*MeshLab filter name*: ‘Matrix: Freeze Current Matrix’

Freeze the current transformation matrix into the coordinates of the vertices of the mesh (and set this matrix to the identity). In other words it applies in a definetive way the current matrix to the vertex coordinates.

**Parameters:**

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

apply\_matrix\_inverse [](#apply_matrix_inverse "Link to this definition")

*MeshLab filter name*: ‘Matrix: Invert Current Matrix’

Invert the current transformation matrix. The current transformation is reversed, becoming its opposite.

**Parameters:**

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

apply\_normal\_normalization\_per\_face [](#apply_normal_normalization_per_face "Link to this definition")

*MeshLab filter name*: ‘Normalize Face Normals’

Normalize Face Normal Lengths to unit vectors.

apply\_normal\_normalization\_per\_vertex [](#apply_normal_normalization_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Normalize Vertex Normals’

Normalize Vertex Normal Lengths to unit vectors.

apply\_normal\_point\_cloud\_smoothing [](#apply_normal_point_cloud_smoothing "Link to this definition")

*MeshLab filter name*: ‘Smooth normals on point sets’

Smooth the normals of the vertices of a mesh without exploiting the triangle connectivity, useful for dataset with no faces

**Parameters:**

`k : int = 10`

> *Number of neighbors*: The number of neighbors used to smooth normals.

`usedist : bool = False`

> *Weight using neighbour distance*: If selected, the neighbour normals are waighted according to their distance

apply\_normal\_smoothing\_per\_face [](#apply_normal_smoothing_per_face "Link to this definition")

*MeshLab filter name*: ‘Smooth Face Normals’

Laplacian smooth of the face normals, without touching the position of the vertices.

apply\_normal\_unsharp\_mask\_per\_vertex [](#apply_normal_unsharp_mask_per_vertex "Link to this definition")

*MeshLab filter name*: ‘UnSharp Mask Normals’

Unsharp mask filtering of the normals per face, putting in more evidence normal variations.  
**A simple normal enhancement technique for interactive non-photorealistic renderings** by *Cignoni, Scopigno and Tarini*, Comput Graph, 29 (1) (2005)  
[doi:10.1016/j.cag.2004.11.012](https://doi.org/10.1016/j.cag.2004.11.012)

**Parameters:**

`recalc : bool = False`

> *Recompute Normals*: Recompute normals from scratch before the unsharp masking

`weight : float = 0.3`

> *Unsharp Weight*: the unsharp weight *w <sub><big>u</big></sub>* in the unsharp mask equation:  
> *w <sub><big>o</big></sub> orig + w <sub><big>u</big></sub> (orig - lowpass)*

`weightorig : float = 1`

> *Original Weight*: How much the original signal is used, e.g. the weight *w <sub><big>o</big></sub>* in the above unsharp mask equation.  
> Usually you should not need to change the default 1.0 value.

`iterations : int = 5`

> *Smooth Iterations*: number of laplacian face smooth iterations in every run

apply\_scalar\_clamping\_per\_vertex [](#apply_scalar_clamping_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Clamp Vertex Quality’

Clamp vertex quality values to a given range according to specific values or to percentiles

**Parameters:**

`minval : float = 0`

> *Min*: The value that will be mapped with the lower end of the scale (red)

`maxval : float = 0`

> *Max*: The value that will be mapped with the upper end of the scale (blue)

`perc : float (bounded) = 0 [min: 0; max: 100]`

> *Percentile Crop \[0..100\]*: If not zero this value will be used for a percentile cropping of the quality values.  
> If this parameter is set to a value *P* then the two values *V\_min,V\_max* for which *P* % of the vertices have a quality **lower or greater** than *V\_min,V\_max* are used as min/max values for clamping.  
>   
> The automated percentile cropping is very useful for automatically discarding outliers.

`zerosym : bool = False`

> *Zero Symmetric*: If true the min max range will be enlarged to be symmetric (so that green is always Zero)

apply\_scalar\_saturation\_per\_vertex [](#apply_scalar_saturation_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Saturate Vertex Quality’

Saturate vertex quality, so that for each vertex the gradient of the quality is lower than the given threshold value (in absolute value)  
The saturation is done in a conservative way (quality is always decreased and never increased)

**Parameters:**

`gradientthr : float = 1`

> *Gradient Threshold*: The maximum value admitted for the quality gradient (in absolute value)

`updatecolor : bool = False`

> *Update ColorMap*: if true the color ramp is computed again

apply\_scalar\_smoothing\_per\_vertex [](#apply_scalar_smoothing_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Smooth Vertex Quality’

Laplacian smooth of the [quality per vertex](https://stackoverflow.com/questions/58610746) values.

apply\_scalar\_unsharp\_mask\_per\_vertex [](#apply_scalar_unsharp_mask_per_vertex "Link to this definition")

*MeshLab filter name*: ‘UnSharp Mask Quality’

Apply Unsharp filter to values of [quality per vertex](https://stackoverflow.com/questions/58610746).  
See [Unsharp Masking](https://en.wikipedia.org/wiki/Unsharp_masking)

**Parameters:**

`weight : float = 0.3`

> *Unsharp Weight*: the unsharp weight *w <sub><big>u</big></sub>* in the unsharp mask equation:  
> *w <sub><big>o</big></sub> orig + w <sub><big>u</big></sub> (orig - lowpass)*

`weightorig : float = 1`

> *Original Weight*: How much the original signal is used, e.g. the weight *w <sub><big>o</big></sub>* in the above unsharp mask equation  
> Usually you should not need to change the default 1.0 value.

`iterations : int = 5`

> *Smooth Iterations*: number of iterations of laplacian smooth in every run

apply\_selection\_by\_same\_connected\_component [](#apply_selection_by_same_connected_component "Link to this definition")

*MeshLab filter name*: ‘Select Connected Faces’

Expand the current face selection so that it includes all the faces in the connected components where there is at least a selected face.

apply\_selection\_dilatation [](#apply_selection_dilatation "Link to this definition")

*MeshLab filter name*: ‘Dilate Selection’

Dilate (expand) the current set of selected faces.

apply\_selection\_erosion [](#apply_selection_erosion "Link to this definition")

*MeshLab filter name*: ‘Erode Selection’

Erode (reduce) the current set of selected faces.

apply\_selection\_inverse [](#apply_selection_inverse "Link to this definition")

*MeshLab filter name*: ‘Invert Selection’

Invert the current set of selected faces/vertices.

**Parameters:**

`invfaces : bool = False`

> *Invert Faces*: If true the filter will invert the set of selected faces.

`invverts : bool = False`

> *Invert Vertices*: If true the filter will invert the set of selected vertices.

apply\_texcoord\_merge\_per\_wedge [](#apply_texcoord_merge_per_wedge "Link to this definition")

*MeshLab filter name*: ‘Merge Wedge Texture Coord’

Merge together per-wedge texture coords that are very close. Used to correct apparent texture seams that can arise from numerical approximations when saving in ascii formats.

**Parameters:**

`mergethr : float = 0.0001`

> *Merging Threshold*: All the per-wedge texture coords that are on the same vertex and are distant less then the given threshold are merged together. It can be used to remove the fake texture seams that arise from error. Distance is in texture space (the default, 1e-4, corresponds to one texel on a 10kx10x texture)

apply\_texmap\_defragmentation [](#apply_texmap_defragmentation "Link to this definition")

*MeshLab filter name*: ‘Texture Map Defragmentation’

Reduces the texture fragmentation by merging atlas charts. The used algorithm is:  
**Texture Defragmentation for Photo-Reconstructed 3D Models**  
*Andrea Maggiordomo, Paolo Cignoni and Marco Tarini*  
Eurographics 2021

**Parameters:**

`matchingthreshold : float = 2`

> *Matching Error Threshold*: Threshold on the seam alignment error. Using a higher threshold can reduce the fragmentation but increase runtime and distortion.

`boundarytolerance : float = 0.2`

> *Seam to chart-boundary-length tolerance*: Cutoff on the minimum fractional seam length. Seams with lower fractional length (relative to the chart perimeter) are not merged to keep the chart borders compact.

`distortiontolerance : float = 0.5`

> *Local ARAP distortion tolerance*: Local UV-optimization distortion tolerance when merging a seam. If the local energy is higher than this value, the operation is reverted.

`globaldistortiontolerance : float = 0.025`

> *Global ARAP distortion tolerance*: Global ARAP distortion tolerance when merging a seam. If the global atlas energy is higher than this value, the operation is reverted.

`uvreductionlimit : float (bounded) = 0 [min: 0; max: 100]`

> *UV Length Target (percentage)*: Target UV length as percentage of the input length. The algorithm halts if the target UV length has be en reached, or if no further seams can be merged.

`offsetfactor : float = 5`

> *Local expansion coefficient*: Coefficient used to control the extension of the UV-optimization area. Larger values can increase the efficacy of the defragmentation, but increase the cost of the geometric optimization and the algorithm runtime.

`timelimit : float = 0`

> *Time limit (seconds)*: Time limit for the defragmentation process (zero means unlimited).

compute\_color\_and\_texture\_from\_active\_rasters\_projection [](#compute_color_and_texture_from_active_rasters_projection "Link to this definition")

*MeshLab filter name*: ‘Project active rasters color to current mesh, filling the texture’

Color information from all the active rasters is perspective-projected on the current mesh, filling the texture, using basic weighting

**Parameters:**

`textname : str = '_color.png'`

> *Texture file*: The texture file to be created

`texsize : int = 1024`

> *pixel size of texture image*: pixel size of texture image, the image will be a square tsize X tsize, most applications do require that tsize is a power of 2

`dorefill : bool = True`

> *fill atlas gaps*: If true, unfilled areas of the mesh are interpolated, to avoid visible seams while mipmapping

`deptheta : float = 0.5`

> *depth threshold*: threshold value for depth buffer projection (shadow buffer)

`onselection : bool = False`

> *Only on selection*: If true, projection is only done for selected vertices

`useangle : bool = True`

> *use angle weight*: If true, color contribution is weighted by pixel view angle

`usedistance : bool = True`

> *use distance weight*: If true, color contribution is weighted by pixel view distance

`useborders : bool = True`

> *use image borders weight*: If true, color contribution is weighted by pixel distance from image boundaries

`usesilhouettes : bool = True`

> *use depth discontinuities weight*: If true, color contribution is weighted by pixel distance from depth discontinuities (external and internal silhouettes)

`usealpha : bool = False`

> *use image alpha weight*: If true, alpha channel of the image is used as additional weight. In this way it is possible to mask-out parts of the images that should not be projected on the mesh. Please note this is not a transparency effect, but just influences the weigthing between different images

compute\_color\_by\_conntected\_component\_per\_face [](#compute_color_by_conntected_component_per_face "Link to this definition")

*MeshLab filter name*: ‘Random Component Color’

Colorize each connected component randomly.

compute\_color\_by\_function\_per\_face [](#compute_color_by_function_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Color Function’

Color function using muparser lib to generate new RGBA color for every face  
Red, Green, Blue and Alpha channels may be defined specifying a function in their respective fields.  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`r : str = '255'`

> *func r =* : function to generate Red component. Expected Range 0-255

`g : str = '0'`

> *func g =* : function to generate Green component. Expected Range 0-255

`b : str = '255'`

> *func b =* : function to generate Blue component. Expected Range 0-255

`a : str = '255'`

> *func alpha =* : function to generate Alpha component. Expected Range 0-255

`onselected : bool = False`

> *only on selection*: if checked, only affects selected faces

compute\_color\_by\_function\_per\_vertex [](#compute_color_by_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Color Function’

Color function using muparser lib to generate new RGBA color for every vertex  
Red, Green, Blue and Alpha channels may be defined specifying a function in their respective fields.  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`x : str = '255'`

> *func r =* : function to generate Red component. Expected Range 0-255

`y : str = '255'`

> *func g =* : function to generate Green component. Expected Range 0-255

`z : str = '0'`

> *func b =* : function to generate Blue component. Expected Range 0-255

`a : str = '255'`

> *func alpha =* : function to generate Alpha component. Expected Range 0-255

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_color\_by\_point\_cloud\_voronoi\_projection [](#compute_color_by_point_cloud_voronoi_projection "Link to this definition")

*MeshLab filter name*: ‘Voronoi Vertex Coloring’

Given a Mesh **M** and a Pointset **P**, The filter project each vertex of P over M and color M according to the geodesic distance from these projected points. Projection and coloring are done on a per vertex basis.

**Parameters:**

`coloredmesh : int = 0`

> *To be Colored Mesh*: The mesh whose surface is colored. For each vertex of this mesh we decide the color according the below parameters.

`vertexmesh : int = 0`

> *Vertex Mesh*: The mesh whose vertices are used as seed points for the color computation. These seeds point are projected onto the above mesh.

`backward : bool = False`

> *BackDistance*: If true the mesh is colored according the distance from the frontier of the voonoi diagram induced by the VertexMesh seeds.

compute\_color\_from\_active\_rasters\_projection [](#compute_color_from_active_rasters_projection "Link to this definition")

*MeshLab filter name*: ‘Project active rasters color to current mesh’

Color information from all the active rasters is perspective-projected on the current mesh using basic weighting

**Parameters:**

`deptheta : float = 0.5`

> *depth threshold*: threshold value for depth buffer projection (shadow buffer)

`onselection : bool = False`

> *Only on selection*: If true, projection is only done for selected vertices

`useangle : bool = True`

> *use angle weight*: If true, color contribution is weighted by pixel view angle

`usedistance : bool = True`

> *use distance weight*: If true, color contribution is weighted by pixel view distance

`useborders : bool = True`

> *use image borders weight*: If true, color contribution is weighted by pixel distance from image boundaries

`usesilhouettes : bool = True`

> *use depth discontinuities weight*: If true, color contribution is weighted by pixel distance from depth discontinuities (external and internal silhouettes)

`usealpha : bool = False`

> *use image alpha weight*: If true, alpha channel of the image is used as additional weight. In this way it is possible to mask-out parts of the images that should not be projected on the mesh. Please note this is not a transparency effect, but just influences the weigthing between different images

`blankcolor : Color = [0; 0; 0; 255]`

> *Color for unprojected areas*: Areas that cannot be projected willb e filled using this color. If R=0 G=0 B=0 A=0 old color is preserved

compute\_color\_from\_current\_raster\_projection [](#compute_color_from_current_raster_projection "Link to this definition")

*MeshLab filter name*: ‘Project current raster color to current mesh’

Color information from the current raster is perspective-projected on the current mesh

**Parameters:**

`usedepth : bool = True`

> *Use depth for projection*: If true, depth is used to restrict projection on visible faces

`deptheta : float = 0.5`

> *depth threshold*: threshold value for depth buffer projection (shadow buffer)

`onselection : bool = False`

> *Only on selection*: If true, projection is only done for selected vertices

`blankcolor : Color = [0; 0; 0; 255]`

> *Color for unprojected areas*: Areas that cannot be projected willb e filled using this color. If R=0 G=0 B=0 A=0 old color is preserved

compute\_color\_from\_scalar\_per\_face [](#compute_color_from_scalar_per_face "Link to this definition")

*MeshLab filter name*: ‘Colorize by face Quality’

Color faces depending on their quality field (manually equalized).

**Parameters:**

`minval : float = 0`

> *Min*: The value that will be mapped with the lower end of the scale (red)

`maxval : float = 0`

> *Max*: The value that will be mapped with the upper end of the scale (blue)

`perc : float (bounded) = 0 [min: 0; max: 100]`

> *Percentile Crop \[0..100\]*: If not zero this value will be used for a percentile cropping of the quality values.  
> If this parameter is set to a value *P* then the two values *V\_min,V\_max* for which *P* % of the faces have a quality **lower or greater** than *V\_min,V\_max* are used as min/max values for clamping.  
>   
> The automated percentile cropping is very useful for automatically discarding outliers.

`zerosym : bool = False`

> *Zero Symmetric*: If true the min max range will be enlarged to be symmetric (so that green is always Zero)

`colormap : str = 'RGB' (or int = 0)`

> Possible enum values:
> 
> > 0. `'RGB'`
> > 1. `'Viridis'`
> > 2. `'Plasma'`
> > 3. `'Cividis'`
> > 4. `'Turbo'`
> > 5. `'RdPu'`
> 
> *Color Map*: The color map to use. RGB is the VCGLib default, other colormaps are sampled from Matplotlib [https://matplotlib.org](https://matplotlib.org/)

compute\_color\_from\_scalar\_per\_vertex [](#compute_color_from_scalar_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize by vertex Quality’

Color vertices depending on their quality field (manually equalized).

**Parameters:**

`minval : float = 0`

> *Min*: The value that will be mapped with the lower end of the scale (red)

`maxval : float = 0`

> *Max*: The value that will be mapped with the upper end of the scale (blue)

`perc : float (bounded) = 0 [min: 0; max: 100]`

> *Percentile Crop \[0..100\]*: If not zero this value will be used for a percentile cropping of the quality values.  
> If this parameter is set to a value *P* then the two values *V\_min,V\_max* for which *P* % of the vertices have a quality **lower or greater** than *V\_min,V\_max* are used as min/max values for clamping.  
>   
> The automated percentile cropping is very useful for automatically discarding outliers.

`zerosym : bool = False`

> *Zero Symmetric*: If true the min max range will be enlarged to be symmetric (so that green is always Zero)

`colormap : str = 'RGB' (or int = 0)`

> Possible enum values:
> 
> > 0. `'RGB'`
> > 1. `'Viridis'`
> > 2. `'Plasma'`
> > 3. `'Cividis'`
> > 4. `'Turbo'`
> > 5. `'RdPu'`
> 
> *Color Map*: The color map to use. RGB is the VCGLib default, other colormaps are sampled from Matplotlib [https://matplotlib.org](https://matplotlib.org/)

compute\_color\_from\_scalar\_using\_transfer\_function\_per\_vertex [](#compute_color_from_scalar_using_transfer_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Quality Mapper applier’

The filter maps quality levels into colors using a colorband built from a transfer function (may be loaded from an external file) and colorizes the mesh vertices. The minimum, medium and maximum quality values can be set by user to obtain a custom quality range for mapping

**Parameters:**

`minqualityval : float = 0`

> *Minimum mesh quality*: The specified quality value is mapped in the **lower** end of the chosen color scale. Default value: the minimum quality value found on the mesh.

`maxqualityval : float = 0`

> *Maximum mesh quality*: The specified quality value is mapped in the **upper** end of the chosen color scale. Default value: the maximum quality value found on the mesh.

`midhandlepos : float = 50`

> *Gamma biasing (0..100)*: Defines a gamma compression of the quality values, by setting the position of the middle of the color scale. Value is defined as a percentage (0..100). Default value is 50, that corresponds to a linear mapping.

`brightness : float = 1`

> *Mesh brightness*: must be between 0 and 2. 0 represents a completely dark mesh, 1 represents a mesh colorized with original colors, 2 represents a completely bright mesh

`tfslist : str = 'Meshlab RGB' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Custom Transfer Function File'`
> > 1. `'Meshlab RGB'`
> > 2. `'RGB'`
> > 3. `'French RGB'`
> > 4. `'Red Scale'`
> > 5. `'Green Scale'`
> > 6. `'Blue Scale'`
> > 7. `'Flat'`
> > 8. `'Saw 4'`
> > 9. `'Saw 8'`
> > 10. `'Grey Scale'`
> 
> *Transfer Function type to apply to filter*: Choose the Transfer Function to apply to the filter

`csvfilename : str = ''`

> *Custom TF Filename*: Filename of the transfer function to be loaded, used only if you have chosen the Custom Transfer Function. Write the full path of the qmap file, or save the file in the same folder of the current mesh, and write only the name of the qmap file. Only the RGB mapping will be imported from the qmap file

compute\_color\_from\_texture\_per\_vertex [](#compute_color_from_texture_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Transfer Color: Texture to Vertex’

Texture to Vertex color transfer

compute\_color\_perlin\_noise\_per\_vertex [](#compute_color_perlin_noise_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Perlin color’

Paints the mesh using PerlinColor function. The color assigned to vertices depends on their position in the space; it means that near vertices will be painted with similar colors.

**Parameters:**

`color1 : Color = [0; 0; 0; 255]`

> *Color 1:*: Sets the first color to mix with Perlin Noise function.

`color2 : Color = [255; 255; 255; 255]`

> *Color 2:*: Sets the second color to mix with Perlin Noise function.

`freq : float (bounded) = 10 [min: 0.1; max: 100]`

> *Frequency:*: Frequency of the Perlin Noise function, expressed as multiples of mesh bbox (frequency 10 means a noise period of bbox diagonal / 10). High frequencies produces many small splashes of colours, while low frequencies produces few big splashes.

`offset : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Offset*: This values is the XYZ frequency offset of the Noise function (offset 1 means 1 period shift).

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

compute\_color\_random\_per\_face [](#compute_color_random_per_face "Link to this definition")

*MeshLab filter name*: ‘Random Face Color’

Colorize Faces randomly. If internal edges are present they are used. Useful for quads.

compute\_color\_scattering\_per\_mesh [](#compute_color_scattering_per_mesh "Link to this definition")

*MeshLab filter name*: ‘PerMesh Color Scattering’

Assigns a random color to each visible mesh layer in the document. Colors change every time the filter is executed, but are always chosen so that they differ as much as possible.

**Parameters:**

`seed : int = 0`

> *Seed*: Random seed used to generate scattered colors. Zero means totally random (each time the filter is started it generates a different result)

compute\_color\_transfer\_face\_to\_vertex [](#compute_color_transfer_face_to_vertex "Link to this definition")

*MeshLab filter name*: ‘Transfer Color: Face to Vertex’

Face to Vertex color transfer

compute\_color\_transfer\_mesh\_to\_face [](#compute_color_transfer_mesh_to_face "Link to this definition")

*MeshLab filter name*: ‘Transfer Color: Mesh to Face’

Mesh to Face color transfer

**Parameters:**

`allvisiblemesh : bool = False`

> *Apply to all Meshes*: If true the color mapping is applied to all the meshes.

compute\_color\_transfer\_vertex\_to\_face [](#compute_color_transfer_vertex_to_face "Link to this definition")

*MeshLab filter name*: ‘Transfer Color: Vertex to Face’

Vertex to Face color transfer

compute\_coord\_by\_function [](#compute_coord_by_function "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Geometric Function’

Geometric function using muparser lib to generate new Coord  
You can change x,y,z for every vertex according to the function specified.  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`x : str = 'x'`

> *func x =* : insert function to generate new coord for x

`y : str = 'y'`

> *func y =* : insert function to generate new coord for y

`z : str = 'sin(x+y)'`

> *func z =* : insert function to generate new coord for z

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_coord\_linear\_morphing [](#compute_coord_linear_morphing "Link to this definition")

*MeshLab filter name*: ‘Vertex Linear Morphing’

Morph deformation of current mesh towards a target mesh with the same number of vertices and same vertex ordering. Each vertex of the source mesh is linearly interpolated towards the corresponding vertex on the target mesh using the formula:

result <sub><big>i</big></sub> = (1-λ)\*source <sub><big>i</big></sub> + λ\*target <sub><big>i</big></sub>

**Three-dimensional metamorphosis: a survey**  
by *F. Lazarus and A. Verroust*, Visual Computer, 1998  
[doi:10.1007/s003710050149](https://doi.org/10.1007/s003710050149)

**Parameters:**

`targetmesh : int = 0`

> *Target Mesh*: The mesh that is the morph target.

`percentmorph : float (bounded) = 0 [min: -150; max: 250]`

> *% Morph*: The percent you want to morph towards (or away from) the target.  
> 0 means current mesh  
> 100 means targe mesh  
> <0 and >100 linearly extrapolate between the two mesh

compute\_curvature\_and\_color\_apss\_per\_vertex [](#compute_curvature_and_color_apss_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize curvature (APSS)’

Colorize the vertices of a mesh or point set using the curvature of the underlying surface.  
  
This is the *algebraic point set surfaces* (APSS) variant which is based on the local fitting of algebraic spheres. It requires points equipped with oriented normals.  
For all the details about APSS see:  
Guennebaud and Gross, 'Algebraic Point Set Surfaces', Siggraph 2007, and  
Guennebaud et al., 'Dynamic Sampling and Rendering of APSS', Eurographics 2008

**Parameters:**

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sphericalparameter : float = 1`

> *MLS - Spherical parameter*: Control the curvature of the fitted spheres: 0 is equivalent to a pure plane fit,1 to a pure spherical fit, values between 0 and 1 gives intermediate results,while other real values might give interesting results, but take care with extremesettings!

`selectiononly : bool = False`

> *Selection only*: If checked, only selected vertices will be projected.

`curvaturetype : str = 'Mean' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Mean'`
> > 1. `'Gauss'`
> > 2. `'K1'`
> > 3. `'K2'`
> > 4. `'ApproxMean'`
> 
> *Curvature type*: The type of the curvature to plot.  
> ApproxMean uses the radius of the fitted sphere as an approximation of the mean curvature.

compute\_curvature\_and\_color\_rimls\_per\_vertex [](#compute_curvature_and_color_rimls_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize curvature (RIMLS)’

Colorize the vertices of a mesh or point set using the curvature of the underlying surface.  
  
This is the Robust Implicit MLS (RIMLS) variant which is an extension of Implicit MLS preserving sharp features using non linear regression. For more details see:  
Oztireli, Guennebaud and Gross, 'Feature Preserving Point Set Surfaces based on Non-Linear Kernel Regression' Eurographics 2009.

**Parameters:**

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sigman : float = 0.75`

> *MLS - Sharpness*: Width of the filter used by the normal refitting weight.This weight function is a Gaussian on the distance between two unit vectors:the current gradient and the input normal. Therefore, typical value range between 0.5 (sharp) to 2 (smooth).

`maxrefittingiters : int = 3`

> *MLS - Max fitting iterations*: Max number of fitting iterations. (0 or 1 is equivalent to the standard IMLS)

`selectiononly : bool = False`

> *Selection only*: If checked, only selected vertices will be projected.

`curvaturetype : str = 'Mean' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Mean'`
> > 1. `'Gauss'`
> > 2. `'K1'`
> > 3. `'K2'`
> 
> *Curvature type*: The type of the curvature to plot.

compute\_curvature\_principal\_directions\_per\_vertex [](#compute_curvature_principal_directions_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Compute curvature principal directions’

Compute the principal directions of curvature with different algorithms

**Parameters:**

`method : str = 'Quadric Fitting' (or int = 3)`

> Possible enum values:
> 
> > 0. `'Taubin approximation'`
> > 1. `'Principal Component Analysis'`
> > 2. `'Normal Cycles'`
> > 3. `'Quadric Fitting'`
> > 4. `'Scale Dependent Quadric Fitting'`
> 
> *Method:*: Choose a method

`curvcolormethod : str = 'Mean Curvature' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Mean Curvature'`
> > 1. `'Gaussian Curvature'`
> > 2. `'Min Curvature'`
> > 3. `'Max Curvature'`
> > 4. `'Shape Index'`
> > 5. `'CurvedNess'`
> > 6. `'None'`
> 
> *Quality/Color Mapping*: Choose the curvature that is mapped into quality and visualized as per vertex color.

`scale : PercentageValue = 10%`

> *Curvature Scale*: This parameter is used only for scale dependent methods: 'Scale Dependent Quadric Fitting' and 'PCA'. It specifies the scale at which the curvature is computed. e.g. for SDQF it specify how large is the patch where we fit the quadric used to compute curvature dirs.

`autoclean : bool = True`

> *Remove Unreferenced Vertices*: If selected, before starting the filter will remove any unreference vertex (for which curvature values are not defined)

compute\_custom\_radius\_scalar\_attribute\_per\_vertex [](#compute_custom_radius_scalar_attribute_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Estimate radius from density’

Estimate the local point spacing (aka radius) around each vertex using a basic estimate of the local density.

**Parameters:**

`nbneighbors : int = 16`

> *Number of neighbors*: Number of neighbors used to estimate the local density. Larger values lead to smoother variations.

compute\_iso\_parametrization [](#compute_iso_parametrization "Link to this definition")

*MeshLab filter name*: ‘Iso Parametrization: Main’

The filter builds the abstract domain mesh representing the Isoparameterization of a watertight two-manifold triangular mesh.  
This abstract mesh can be used to uniformly remesh the input mesh, or to build a atlased texture parametrization. Abstract Mesh can be also loaded and saved.  
In short this filter build a very coarse almost regular triangulation such that original mesh can be reprojected from this abstract mesh with minimal distortion.  
For more details see:  
**N. Pietroni, M. Tarini and P. Cignoni**,  
['Almost isometric mesh parameterization through abstract domains'](http://vcg.isti.cnr.it/Publications/2010/PTC10/)  
IEEE Transaction of Visualization and Computer Graphics, 2010

**Parameters:**

`targetabstractminfacenum : int = 150`

> *AM Min Size*: This number and the following one indicate the range face number of the abstract mesh that is used for the parametrization process.  
> The algorithm will choose the best abstract mesh with the number of triangles within the specified interval.  
> If the mesh has a very simple structure this range can be very low and strict;for a roughly spherical object if you can specify a range of \[8,8\] faces you get a octahedral abstract mesh, e.g. a geometry image.  
> Large numbers (greater than 400) are usually not of practical use.

`targetabstractmaxfacenum : int = 200`

> *AM Max Size*: Please notice that a large interval requires huge amount of memory to be allocated, in order save the intermediate results.  
> An interval of 50 should be fine.

`stopcriteria : str = 'Area + Angle' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Best Heuristic'`
> > 1. `'Area + Angle'`
> > 2. `'Regularity'`
> > 3. `'L2'`
> 
> *Optimization Criteria*: Choose a metric to stop the parametrization within the interval  
> 1: Best Heuristic: stop considering both isometry and number of faces of base domain  
> 2: Area + Angle: stop at minimum area and angle distorsion  
> 3: Regularity: stop at minimum number of irregular vertices  
> 4: L2: stop at minimum OneWay L2 Stretch Eff

`convergencespeed : int = 1`

> *Convergence Precision*: This parameter controls the convergence speed/precision of the optimization of the texture coordinates. Larger the number slower the processing and, eventually, slightly better results

`doublestep : bool = True`

> *Double Step*: Use this bool to divide the parameterization in 2 steps. Double step makes the overall process faster and robust.  
> Consider to disable this bool in case the object has topologycal noise or small handles.

compute\_matrix\_by\_fitting\_to\_plane [](#compute_matrix_by_fitting_to_plane "Link to this definition")

*MeshLab filter name*: ‘Transform: Rotate to Fit to a plane’

Generate a matrix transformation that rotates the mesh so that the selection fits one of the main planes XY YZ ZX. May also translate such that the selection centroid rest on the origin. It reports on the log the average error of the fitting (in mesh units).

**Parameters:**

`targetplane : str = 'XY plane' (or int = 0)`

> Possible enum values:
> 
> > 0. `'XY plane'`
> > 1. `'YZ plane'`
> > 2. `'ZX plane'`
> 
> *Rotate to fit:*: Choose the plane where the selection will fit

`rotaxis : str = 'any axis' (or int = 0)`

> Possible enum values:
> 
> > 0. `'any axis'`
> > 1. `'X axis'`
> > 2. `'Y axis'`
> > 3. `'Z axis'`
> 
> *Rotate on:*: Choose on which axis do the rotation: 'any axis' guarantee the best fit of the selection to the plane, only use X,Y or Z it if you want to preserve that specific axis.

`toorigin : bool = True`

> *Move to Origin*: Also apply a translation, such that the centroid of selection rests on the Origin

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_matrix\_by\_icp\_between\_meshes [](#compute_matrix_by_icp_between_meshes "Link to this definition")

*MeshLab filter name*: ‘ICP Between Meshes’

Perform the ICP algorithm to minimize the difference between two cloud of points.

**Parameters:**

`referencemesh : int = 0`

> *Reference Mesh*: The Reference Mesh is the point cloud kept fixed during the ICP process.

`sourcemesh : int = 1`

> *Source Mesh*: The Source Mesh is the point cloud which will be roto-translated to match the Reference Mesh.

`samplenum : int = 2000`

> *Sample Number*: Number of samples that we try to choose at each ICP iteration

`mindistabs : float = 10`

> *Minimal Starting Distance*: For all the chosen sample on one mesh we consider for ICP only the samples nearer than this value.If MSD is too large outliers could be included, if it is too small convergence will be very slow. A good guess is needed here, suggested values are in the range of 10-100 times of the device scanning error.This value is also dynamically changed by the 'Reduce Distance Factor'

`trgdistabs : float = 0.005`

> *Target Distance*: When 50% of the chosen samples are below this distance we consider the two mesh aligned. Usually it should be a value lower than the error of the scanning device.

`maxiternum : int = 75`

> *Max Iteration Num*: The maximum number of iteration that the ICP is allowed to perform.

`samplemode : bool = True`

> *Normal Equalized Sampling*: if true (default) the sample points of icp are chosen with a distribution uniform with respect to the normals of the surface. Otherwise they are distributed in a spatially uniform way.

`reducefactorperc : float = 0.8`

> *MSD Reduce Factor*: At each ICP iteration the Minimal Starting Distance is reduced to be 5 times the percentile of the sample distances (e.g. if RF is 0.9 the new Minimal Starting Distance is 5 times the value such that 90% of the sample lies at a distance lower than .

`passhifilter : float = 0.75`

> *Sample Cut High*: At each ICP iteration all the sample that are farther than the percentile are discarded ( In practice we use only the best results ).

`matchmode : bool = True`

> *Rigid matching*: If true the ICP is constrained to perform matching only through roto-translations (no scaling allowed). If false a more relaxed transformation matrix is allowed (scaling and shearing can appear).

`savelastiteration : bool = False`

> *Save Last Iteration*: Toggle this checkbox in order to save the last iteration points in two layers.

compute\_matrix\_by\_mesh\_global\_alignment [](#compute_matrix_by_mesh_global_alignment "Link to this definition")

*MeshLab filter name*: ‘Global Align Meshes’

Perform the global alignment process to align a set of visible meshes together. The alignment algorithm is implemented over the idea written by *Kari Pulli* in his paper: "Multiview Registration for Large Data Sets"

**Parameters:**

`basemesh : int = 0`

> *Base Mesh*: The base mesh is the one who will stay fixed during the alignment process.

`onlyvisiblemeshes : bool = False`

> *Only visible meshes*: Apply the global alignment only to the visible meshes

`ogsize : int = 50000`

> *Occupancy Grid Size*: To compute the overlap between range maps we discretize them into voxel and count them (both for area and overlap); This parameter affect the resolution of the voxelization process. Using a too fine voxelization can...

`arcthreshold : float = 0.3`

> *Arc Area Thr.*: We run ICP on every pair of mesh with a relative overlap greater than this threshold. The relative overlap is computed as overlapArea / min(area1,area2)

`recalcthreshold : float = 0.1`

> *Recalc Fraction*: Every time we start process we discard the fraction of all the arcs in order to recompute them and hopefully improve the final result. It corresponds to iteratively recalc the bad arcs.

`samplenum : int = 2000`

> *Sample Number*: Number of samples that we try to choose at each ICP iteration

`mindistabs : float = 10`

> *Minimal Starting Distance*: For all the chosen sample on one mesh we consider for ICP only the samples nearer than this value.If MSD is too large outliers could be included, if it is too small convergence will be very slow. A good guess is needed here, suggested values are in the range of 10-100 times of the device scanning error.This value is also dynamically changed by the 'Reduce Distance Factor'

`trgdistabs : float = 0.005`

> *Target Distance*: When 50% of the chosen samples are below this distance we consider the two mesh aligned. Usually it should be a value lower than the error of the scanning device.

`maxiternum : int = 75`

> *Max Iteration Num*: The maximum number of iteration that the ICP is allowed to perform.

`samplemode : bool = True`

> *Normal Equalized Sampling*: if true (default) the sample points of icp are chosen with a distribution uniform with respect to the normals of the surface. Otherwise they are distributed in a spatially uniform way.

`reducefactorperc : float = 0.8`

> *MSD Reduce Factor*: At each ICP iteration the Minimal Starting Distance is reduced to be 5 times the percentile of the sample distances (e.g. if RF is 0.9 the new Minimal Starting Distance is 5 times the value such that 90% of the sample lies at a distance lower than .

`passhifilter : float = 0.75`

> *Sample Cut High*: At each ICP iteration all the sample that are farther than the percentile are discarded ( In practice we use only the best results ).

`matchmode : bool = True`

> *Rigid matching*: If true the ICP is constrained to perform matching only through roto-translations (no scaling allowed). If false a more relaxed transformation matrix is allowed (scaling and shearing can appear).

compute\_matrix\_by\_principal\_axis [](#compute_matrix_by_principal_axis "Link to this definition")

*MeshLab filter name*: ‘Transform: Align to Principal Axis’

Generate a matrix transformation that rotates the mesh aligning it to its principal axis of inertia.If the mesh is watertight the Itertia tensor is computed assuming the interior of the mesh has a uniform density.In case of an open mesh or a point clouds the inerta tensor is computed assuming each vertex is a constant puntual mass.

**Parameters:**

`pointsflag : bool = True`

> *Use vertex*: If selected, only the vertices of the mesh are used to compute the Principal Axis. Mandatory for point clouds or for non water tight meshes

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_matrix\_from\_rotation [](#compute_matrix_from_rotation "Link to this definition")

*MeshLab filter name*: ‘Transform: Rotate’

Generate a matrix transformation that rotates the mesh. The mesh can be rotated around one of the axis or a given axis and w.r.t. to the origin or the baricenter, or a given point.

**Parameters:**

`rotaxis : str = 'X axis' (or int = 0)`

> Possible enum values:
> 
> > 0. `'X axis'`
> > 1. `'Y axis'`
> > 2. `'Z axis'`
> > 3. `'custom axis'`
> 
> *Rotation on:*: Choose a method

`rotcenter : str = 'origin' (or int = 0)`

> Possible enum values:
> 
> > 0. `'origin'`
> > 1. `'barycenter'`
> > 2. `'custom point'`
> 
> *Center of rotation:*: Choose a method

`angle : float (bounded) = 0 [min: -360; max: 360]`

> *Rotation Angle*: Angle of rotation (in **degree**). If snapping is enabled this value is rounded according to the snap value

`customaxis : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom axis*: This rotation axis is used only if the 'custom axis' option is chosen.

`customcenter : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom center*: This rotation center is used only if the 'custom point' option is chosen.

`snapflag : bool = False`

> *Snap angle*: If selected, before starting the filter will remove any unreferenced vertex (for which curvature values are not defined)

`snapangle : float = 30`

> *Snapping Value*: This value is used to snap the rotation angle (i.e. if the snapping value is 30, 227 becomes 210).

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_matrix\_from\_scaling\_or\_normalization [](#compute_matrix_from_scaling_or_normalization "Link to this definition")

*MeshLab filter name*: ‘Transform: Scale, Normalize’

Generate a matrix transformation that scale the mesh. The mesh can be also automatically scaled to a unit side box.

**Parameters:**

`axisx : float = 1`

> *X Axis*: Scaling

`axisy : float = 1`

> *Y Axis*: Scaling

`axisz : float = 1`

> *Z Axis*: Scaling

`uniformflag : bool = True`

> *Uniform Scaling*: If selected an uniform scaling (the same for all the three axis) is applied (the X axis value is used)

`scalecenter : str = 'origin' (or int = 0)`

> Possible enum values:
> 
> > 0. `'origin'`
> > 1. `'barycenter'`
> > 2. `'custom point'`
> 
> *Center of scaling:*: Choose a method

`customcenter : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Custom center*: This scaling center is used only if the 'custom point' option is chosen.

`unitflag : bool = False`

> *Scale to Unit bbox*: If selected, the object is scaled to a box whose sides are at most 1 unit length

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_matrix\_from\_translation [](#compute_matrix_from_translation "Link to this definition")

*MeshLab filter name*: ‘Transform: Translate, Center, set Origin’

Generate a matrix transformation that translate the mesh. The mesh can be translated around one of the axis or a given axis and w.r.t. to the origin or the baricenter, or a given point.

**Parameters:**

`traslmethod : str = 'XYZ translation' (or int = 0)`

> Possible enum values:
> 
> > 0. `'XYZ translation'`
> > 1. `'Center on Scene BBox'`
> > 2. `'Center on Layer BBox'`
> > 3. `'Set new Origin'`
> 
> *Transformation:*: \[XYZ translation\] adds X,Y and Z offset to Layer transformation, \[Center on BBox\] moves Layer Origin to the Bounding Box center, \[Set new Origin\] moves Layer Origin to a specific point

`axisx : float (bounded) = 0 [min: -8.66025; max: 8.66025]`

> *X Axis*: when using \[XYZ translation\], amount of translation along the X axis (in model units)

`axisy : float (bounded) = 0 [min: -8.66025; max: 8.66025]`

> *Y Axis*: when using \[XYZ translation\], amount of translation along the Y axis (in model units)

`axisz : float (bounded) = 0 [min: -8.66025; max: 8.66025]`

> *Z Axis*: when using \[XYZ translation\], amount of translation along the Z axis (in model units)

`neworigin : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *New Origin:*: when using \[Set new Origin\], this is the location of the new Origin.

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_matrix\_from\_translation\_rotation\_scale [](#compute_matrix_from_translation_rotation_scale "Link to this definition")

*MeshLab filter name*: ‘Matrix: Set from translation/rotation/scale’

Set the current transformation matrix starting from parameters: \[XYZ\] translation, \[XYZ\] Euler angles rotation and \[XYZ\] scaling.

**Parameters:**

`translationx : float = 0`

> *X Translation*: Translation factor on X axis

`translationy : float = 0`

> *Y Translation*: Translation factor on Y axis

`translationz : float = 0`

> *Z Translation*: Translation factor on Z axis

`rotationx : float = 0`

> *X Rotation*: Rotation angle on X axis

`rotationy : float = 0`

> *Y Rotation*: Rotation angle on Y axis

`rotationz : float = 0`

> *Z Rotation*: Rotation angle on Z axis

`scalex : float = 1`

> *X Scale*: Scaling factor on X axis

`scaley : float = 1`

> *Y Scale*: Scaling factor on Y axis

`scalez : float = 1`

> *Z Scale*: Scaling factor on Z axis

`compose : bool = False`

> *Compose with current*: If selected, the new matrix will be composed with the current one (matrix=new\*old)

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

compute\_mls\_projection\_apss [](#compute_mls_projection_apss "Link to this definition")

*MeshLab filter name*: ‘MLS projection (APSS)’

Project a mesh (or a point set) onto the MLS surface defined by itself or another point set.  
  
This is the *algebraic point set surfaces* (APSS) variant which is based on the local fitting of algebraic spheres. It requires points equipped with oriented normals.  
For all the details about APSS see:  
Guennebaud and Gross, 'Algebraic Point Set Surfaces', Siggraph 2007, and  
Guennebaud et al., 'Dynamic Sampling and Rendering of APSS', Eurographics 2008

**Parameters:**

`controlmesh : int = 0`

> *Point set*: The point set (or mesh) which defines the MLS surface.

`proxymesh : int = 0`

> *Proxy Mesh*: The mesh that will be projected/resampled onto the MLS surface.

`selectiononly : bool = False`

> *Selection only*: If checked, only selected vertices will be projected.

`maxsubdivisions : int = 0`

> *Refinement - Max subdivisions*: Max number of subdivisions.

`thangleindegree : float = 2`

> *Refinement - Crease angle (degree)*: Threshold angle between two faces controlling the refinement.

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sphericalparameter : float = 1`

> *MLS - Spherical parameter*: Control the curvature of the fitted spheres: 0 is equivalent to a pure plane fit,1 to a pure spherical fit, values between 0 and 1 gives intermediate results,while other real values might give interesting results, but take care with extremesettings!

`accuratenormal : bool = True`

> *Accurate normals*: If checked, use the accurate MLS gradient instead of the local approximationto compute the normals.

compute\_mls\_projection\_rimls [](#compute_mls_projection_rimls "Link to this definition")

*MeshLab filter name*: ‘MLS projection (RIMLS)’

Project a mesh (or a point set) onto the MLS surface defined by itself or another point set.  
  
This is the Robust Implicit MLS (RIMLS) variant which is an extension of Implicit MLS preserving sharp features using non linear regression. For more details see:  
Oztireli, Guennebaud and Gross, 'Feature Preserving Point Set Surfaces based on Non-Linear Kernel Regression' Eurographics 2009.

**Parameters:**

`controlmesh : int = 0`

> *Point set*: The point set (or mesh) which defines the MLS surface.

`proxymesh : int = 0`

> *Proxy Mesh*: The mesh that will be projected/resampled onto the MLS surface.

`selectiononly : bool = False`

> *Selection only*: If checked, only selected vertices will be projected.

`maxsubdivisions : int = 0`

> *Refinement - Max subdivisions*: Max number of subdivisions.

`thangleindegree : float = 2`

> *Refinement - Crease angle (degree)*: Threshold angle between two faces controlling the refinement.

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sigman : float = 0.75`

> *MLS - Sharpness*: Width of the filter used by the normal refitting weight.This weight function is a Gaussian on the distance between two unit vectors:the current gradient and the input normal. Therefore, typical value range between 0.5 (sharp) to 2 (smooth).

`maxrefittingiters : int = 3`

> *MLS - Max fitting iterations*: Max number of fitting iterations. (0 or 1 is equivalent to the standard IMLS)

compute\_new\_custom\_point\_attribute\_per\_face [](#compute_new_custom_point_attribute_per_face "Link to this definition")

*MeshLab filter name*: ‘Define New Per Face Custom Point Attribute’

Add a new Per-Face custom point attribute to current mesh and fill it with the defined functions.  
Attribute names must contain only letters, numbers and underscores.  
The name specified for the attribute can be used in other filter functions.  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`name : str = 'CustomAttrName'`

> *Name*: the name of new attribute. you can access attribute in other filters through this name

`x_expr : str = 'x0'`

> *x coord function =*: function to calculate custom x coord of the point attribute value for each face

`y_expr : str = 'y0'`

> *y coord function =*: function to calculate custom y coord of the point attribute value for each face

`z_expr : str = 'z0'`

> *z coord function =*: function to calculate custom z coord of the point attribute value for each face

compute\_new\_custom\_point\_attribute\_per\_vertex [](#compute_new_custom_point_attribute_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Define New Per Vertex Custom Point Attribute’

Add a new Per-Vertex custom point attribute to current mesh and fill it with the defined functions.  
Attribute names must contain only letters, numbers and underscores.  
The name specified for the attribute can be used in other filter functions.  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`name : str = 'CustomAttrName'`

> *Name*: the name of new attribute. you can access attribute in other filters through this name

`x_expr : str = 'x'`

> *x coord function =*: function to calculate custom x coord of the point attribute value for each vertex

`y_expr : str = 'y'`

> *y coord function =*: function to calculate custom y coord of the point attribute value for each vertex

`z_expr : str = 'z'`

> *z coord function =*: function to calculate custom z coord of the point attribute value for each vertex

compute\_new\_custom\_scalar\_attribute\_per\_face [](#compute_new_custom_scalar_attribute_per_face "Link to this definition")

*MeshLab filter name*: ‘Define New Per Face Custom Scalar Attribute’

Add a new Per-Face custom scalar attribute to current mesh and fill it with the defined function.  
Attribute names must contain only letters, numbers and underscores.  
The name specified for the attribute can be used in other filter functions.  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`name : str = 'CustomAttrName'`

> *Name*: the name of new attribute. you can access attribute in other filters through this name

`expr : str = 'fi'`

> *Scalar function =*: function to calculate custom scalar attribute value for each face

compute\_new\_custom\_scalar\_attribute\_per\_vertex [](#compute_new_custom_scalar_attribute_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Define New Per Vertex Custom Scalar Attribute’

Add a new Per-Vertex custom scalar attribute to current mesh and fill it with the defined function.  
Attribute names must contain only letters, numbers and underscores.  
The name specified for the attribute can be used in other filter functions.  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`name : str = 'CustomAttrName'`

> *Name*: the name of new attribute. you can access attribute in other filters through this name

`expr : str = 'x'`

> *Scalar function =*: function to calculate custom scalar attribute value for each vertex

compute\_normal\_by\_function\_per\_face [](#compute_normal_by_function_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Normal Function’

Normal function using muparser to generate new Normal for every face  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`x : str = '-fnx'`

> *func nx =* : insert function to generate new x for the normal

`y : str = '-fny'`

> *func ny =* : insert function to generate new y for the normal

`z : str = '-fnz'`

> *func nz =* : insert function to generate new z for the normal

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_normal\_by\_function\_per\_vertex [](#compute_normal_by_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Normal Function’

Normal function using muparser to generate new Normal for every vertex  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`x : str = '-nx'`

> *func nx =* : insert function to generate new x for the normal

`y : str = '-ny'`

> *func ny =* : insert function to generate new y for the normal

`z : str = '-nz'`

> *func nz =* : insert function to generate new z for the normal

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_normal\_for\_point\_clouds [](#compute_normal_for_point_clouds "Link to this definition")

*MeshLab filter name*: ‘Compute normals for point sets’

Compute the normals of the vertices of a mesh without exploiting the triangle connectivity, useful for dataset with no faces

**Parameters:**

`k : int = 10`

> *Neighbour num*: The number of neighbors used to estimate normals.

`smoothiter : int = 0`

> *Smooth Iteration*: The number of smoothing iteration done on the p used to estimate and propagate normals.

`flipflag : bool = False`

> *Flip normals w.r.t. viewpoint*: If the 'viewpoint' (i.e. scanner position) is known, it can be used to disambiguate normals orientation, so that all the normals will be oriented in the same direction.

`viewpos : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Viewpoint Pos.*: The viewpoint position can be set by hand (i.e. getting the current viewpoint) or it can be retrieved from mesh camera, if the viewpoint position is stored there.

compute\_normal\_from\_cameras\_per\_vertex [](#compute_normal_from_cameras_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Re-Orient vertex normals using cameras’

Reorient vertex normals using cameras. For this filter to work the mesh needs to have the attribute 'correspondences' which is only created when loading Bundler files (.out projects)

compute\_normal\_per\_face [](#compute_normal_per_face "Link to this definition")

*MeshLab filter name*: ‘Re-Compute Face Normals’

Recompute face normals as the normal of the plane of the face.  
See [How to find surface normal of a triangle](https://math.stackexchange.com/questions/305642/)

compute\_normal\_per\_vertex [](#compute_normal_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Re-Compute Vertex Normals’

Recompute vertex normals according to four different schemes:  
1) Simple (no weights) average of normals of the incident faces  
2) Area weighted average of normals of the incident faces  
3) Angle weighted sum of normals of the incident faces according to the article **\[1\]**. Probably this is the best all-purpose choice. It could slightly bias the result for degenerate, fat triangles.  
4) Weighted sum of normals of the incident faces, as defined by article **\[2\]**. The weight for each wedge is the cross product of the two edges over the product of the square of the two edge lengths.According to the original article it is perfect only for spherical surface, but it should perform well also in practice.  
\[1\]: **Computing Vertex Normals from Polygonal Facet** by *G Thurmer and CA Wuthrich*, JGT volume3, num 1. 1998  
[doi:10.1080/10867651.1998.10487487](https://doi.org/10.1080/10867651.1998.10487487)  
\[2\]: **Weights for Computing Vertex Normals from Facet Normals** by *Nelson Max*, JGT vol4, num 2. 1999  
[doi:10.1080/10867651.1999.10487501](https://doi.org/10.1080/10867651.1999.10487501)

**Parameters:**

`weightmode : str = 'Simple Average' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Simple Average'`
> > 1. `'By Area'`
> > 2. `'By Angle'`
> > 3. `'As defined by N. Max'`
> 
> *Weighting Mode:*:

compute\_normal\_polygon\_mesh\_per\_face [](#compute_normal_polygon_mesh_per_face "Link to this definition")

*MeshLab filter name*: ‘Re-Compute Per-Polygon Face Normals’

Recompute face normals as the average of the normals of the triangles that builds a polygon. Useful for showing uniformly shaded quad or polygonal meshes represented using [faux edges](https://stackoverflow.com/questions/59392193).

compute\_scalar\_ambient\_occlusion [](#compute_scalar_ambient_occlusion "Link to this definition")

*MeshLab filter name*: ‘Compute Ambient occlusion’

Compute Ambient Occlusion.This filter is a shading technique used in computer graphics to simulate the way light interacts with surfaces in a realistic manner.The parameter for the number of rays is defined by the user; this parameter represents the number of rays that will be shot from the barycenter of each face.The higher the number of rays, the longer the time to compute, but the better the results.These results are saved into face quality and mapped into a gray shade on the mesh.This filter uses the Embree3 library by INTEL.

**Parameters:**

`rays : int = 64`

> *Number of rays*: The number of rays shoot from the barycenter of the face. The higher the number the higher the definition of the ambient occlusion but at the cost of the calculation time

compute\_scalar\_ambient\_occlusion\_gpu [](#compute_scalar_ambient_occlusion_gpu "Link to this definition")

*MeshLab filter name*: ‘Ambient Occlusion’

Compute ambient occlusions values; it takes a number of well distributed view direction and for point of the surface it computes how many time it is visible from these directions. This value is saved into quality and automatically mapped into a gray shade. The average direction is saved into an attribute named 'BentNormal'

**Parameters:**

`occmode : str = 'per-Vertex' (or int = 0)`

> Possible enum values:
> 
> > 0. `'per-Vertex'`
> > 1. `'per-Face (deprecated)'`
> 
> *Occlusion mode:*: Occlusion may be calculated per-vertex or per-face, color and quality will be saved in the chosen component.

`dirbias : float = 0`

> *Directional Bias \[0..1\]*: The balance between a uniform and a directionally biased set of lighting direction  
> : - 0 means light came only uniformly from any direction  
> \- 1 means that all the light cames from the specified cone of directions  
> \- other values mix the two set of lighting directions

`reqviews : int = 128`

> *Requested views*: Number of different views uniformly placed around the mesh. More views means better accuracy at the cost of increased calculation time

`conedir : numpy.ndarray[numpy.float64[3]] = [0, 1, 0]`

> *Lighting Direction*: Number of different views placed around the mesh. More views means better accuracy at the cost of increased calculation time

`coneangle : float = 30`

> *Cone amplitude*: Number of different views uniformly placed around the mesh. More views means better accuracy at the cost of increased calculation time

`usegpu : bool = False`

> *Use GPU acceleration*: Only works for per-vertex AO. In order to use GPU-Mode, your hardware must support FBOs, FP32 Textures and Shaders. Normally increases the performance by a factor of 4x-5x

`depthtexsize : int = 512`

> *Depth texture size(should be 2^n)*: Defines the depth texture size used to compute occlusion from each point of view. Higher values means better accuracy usually with low impact on performance

compute\_scalar\_by\_aspect\_ratio\_per\_face [](#compute_scalar_by_aspect_ratio_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Quality according to Triangle shape and aspect ratio’

Compute a quality and colorize faces depending on triangle shape:
1. area/max side of triangle
2. ratio inradius/circumradius (radii of incircle and circumcircle)
3. Mean ratio of triangle = area/(a\*a + b\*b + c\*c)
4. Area
5. Texture Angle Distortion. Difference between angle in 3D space and texture space
6. Texture Area Distortion. Difference between area in 3D space and texture space
7. Polygonal Planarity (max distance to support plane)
8. Polygonal Planarity (relative distance to support plane)

**Parameters:**

`metric : str = 'area/max side' (or int = 0)`

> Possible enum values:
> 
> > 0. `'area/max side'`
> > 1. `'inradius/circumradius'`
> > 2. `'Mean ratio'`
> > 3. `'Area'`
> > 4. `'Texture Angle Distortion'`
> > 5. `'Texture Area Distortion'`
> > 6. `'Polygonal planarity (max)'`
> > 7. `'Polygonal planarity (relative)'`
> 
> *Metric:*: Choose a metric to compute triangle quality.

compute\_scalar\_by\_border\_distance\_per\_vertex [](#compute_scalar_by_border_distance_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize by border distance’

Store in the quality field the geodesic distance from borders and color the mesh accordingly.

compute\_scalar\_by\_discrete\_curvature\_per\_vertex [](#compute_scalar_by_discrete_curvature_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Discrete Curvatures’

Colorize according to various discrete curvature computed as described in:  
' *Discrete Differential-Geometry Operators for Triangulated 2-Manifolds* '  
M. Meyer, M. Desbrun, P. Schroder, A. H. Barr

**Parameters:**

`curvaturetype : str = 'Mean Curvature' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Mean Curvature'`
> > 1. `'Gaussian Curvature'`
> > 2. `'RMS Curvature'`
> > 3. `'ABS Curvature'`
> 
> *Type:*: Choose the curvature value that you want transferred onto the scalar Quality.Mean (H) and Gaussian (K) curvature are computed according the technique described in the Desbrun et al. paper.  
> Absolute curvature is defined as |H|+|K| and RMS curvature as sqrt(4\* H^2 - 2K) as explained in  
> *Improved curvature estimationfor watershed segmentation of 3-dimensional meshes* by S. Pulla, A. Razdan, G. Farin.

compute\_scalar\_by\_distance\_from\_another\_mesh\_per\_vertex [](#compute_scalar_by_distance_from_another_mesh_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Distance from Reference Mesh’

Compute the signed/unsigned (per vertex) distance between a mesh/pointcloud and a reference mesh/pointcloud. Distance is stored in vertex quality.

**Parameters:**

`measuremesh : int = 0`

> *Measured Mesh/PointCloud*: The Mesh/Pointcloud that is measured, vertex by vertex, computing distance from the REFERENCE mesh/pointcloud.

`refmesh : int = 0`

> *Reference Mesh/PointCloud*: The Mesh/Pointcloud that is used as a reference, to measure distance from.

`signeddist : bool = True`

> *Compute Signed Distance*: If TRUE, the distance is signed; if FALSE, it will compute the distance absolute value.

`maxdist : PercentageValue = 100%`

> *Max Distance \[abs\]*: Search is interrupted when nothing is found within this distance range \[+maxDistance -maxDistance\].

compute\_scalar\_by\_distance\_from\_point\_cloud\_per\_vertex [](#compute_scalar_by_distance_from_point_cloud_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Disk Vertex Coloring’

Given a Mesh **M** and a Pointset **P**, The filter project each vertex of P over M and color M according to the Euclidean distance from these projected points. Projection and coloring are done on a per vertex basis.

**Parameters:**

`coloredmesh : int = 0`

> *To be Colored Mesh*: The mesh whose surface is colored. For each vertex of this mesh we decide the color according the below parameters.

`vertexmesh : int = 0`

> *Vertex Mesh*: The mesh whose vertices are used as seed points for the color computation. These seeds point are projected onto the above mesh.

`radius : float (bounded) = 0.173205 [min: 0; max: 0.57735]`

> *Radius*: the radius of the spheres centered in the VertexMesh seeds

`sampleradius : bool = False`

> *Use sample radius*: Use the radius that is stored in each sample of the vertex mesh. Useful for displaing the variable disk sampling results

`approximategeodetic : bool = False`

> *Use Approximate Geodetic*: Use the Approximate Geodetic Metric instead of the Euclidean distance. Approximate geodetic metric uses the normals between the two points to weight the euclidean distance.

compute\_scalar\_by\_function\_per\_face [](#compute_scalar_by_function_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Quality Function’

Quality function using muparser to generate new Quality for every face  
Insert three function each one for quality of the three vertex of a face  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`q : str = 'x0+y0+z0'`

> *func q0 =* : function to generate new Quality foreach face

`normalize : bool = False`

> *normalize*: if checked normalize all quality values in range \[0..1\]

`map : bool = False`

> *map into color*: if checked map quality generated values into per-vertex color

`onselected : bool = False`

> *only on selection*: if checked, only affects selected faces

compute\_scalar\_by\_function\_per\_vertex [](#compute_scalar_by_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Quality Function’

Quality function using muparser to generate new Quality for every vertex  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`q : str = 'vi'`

> *func q =* : function to generate new Quality for every vertex

`normalize : bool = False`

> *normalize*: if checked normalize all quality values in range \[0..1\]

`map : bool = False`

> *map into color*: if checked map quality generated values into per-vertex color

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_scalar\_by\_geodesic\_distance\_from\_given\_point\_per\_vertex [](#compute_scalar_by_geodesic_distance_from_given_point_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize by geodesic distance from a given point’

Store in the quality field the geodesic distance from a given point on the mesh surface and color the mesh accordingly.

**Parameters:**

`startpoint : numpy.ndarray[numpy.float64[3]] = [-0.5, -0.5, -0.5]`

> *Starting point*: The starting point from which geodesic distance has to be computed. If it is not a surface vertex, the closest vertex to the specified point is used as starting seed point.

`maxdistance : PercentageValue = 50%`

> *Max Distance*: If not zero it indicates a cut off value to be used during geodesic distance computation.

compute\_scalar\_by\_geodesic\_distance\_from\_selection\_per\_vertex [](#compute_scalar_by_geodesic_distance_from_selection_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize by geodesic distance from the selected points’

Store in the quality field the geodesic distance from the selected points on the mesh surface and color the mesh accordingly.

**Parameters:**

`maxdistance : PercentageValue = 50%`

> *Max Distance*: If not zero it indicates a cut off value to be used during geodesic distance computation.

compute\_scalar\_by\_heat\_geodesic\_distance\_from\_selection\_per\_vertex [](#compute_scalar_by_heat_geodesic_distance_from_selection_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Colorize by approximated geodesic distance from the selected points’

Store in the quality field the approximated geodesic distance, computed via heat method (Crane et al.), from the selected points on the mesh surface and color the mesh accordingly. As this implementation does not use intrinsic triangulation it is very sensitive to trinagulation. First run takes longer as factorization has to be build.

**Parameters:**

`m : float = 1`

> *Euler Step*: Multiplier used in backward Euler timestep. Changing this value will reset the cache.

compute\_scalar\_by\_scalar\_harmonic\_field\_per\_vertex [](#compute_scalar_by_scalar_harmonic_field_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Generate Scalar Harmonic Field’

Generates a scalar harmonic field over the mesh. Input scalar values must be assigned to two vertices as Dirichlet boundary conditions. Applying the filter, a discrete Laplace operator generates the harmonic field values for all the mesh vertices, which are stored in the [quality per vertex attribute](https://stackoverflow.com/questions/58610746) of the mesh.  
For more details see:**Dynamic Harmonic Fields for Surface Processing** by *Kai Xua, Hao Zhang, Daniel Cohen-Or, Yueshan Xionga*. Computers & Graphics, 2009  
[doi:10.1016/j.cag.2009.03.022](https://doi.org/10.1016/j.cag.2009.03.022)

**Parameters:**

`point1 : numpy.ndarray[numpy.float64[3]] = [-0.5, -0.5, -0.5]`

> *Point 1*: A vertex on the mesh that represent one harmonic field boundary condition.

`point2 : numpy.ndarray[numpy.float64[3]] = [0.5, 0.5, 0.5]`

> *Point 2*: A vertex on the mesh that represent one harmonic field boundary condition.

`value1 : float (bounded) = 0 [min: 0; max: 1]`

> *value for the 1st point*: Harmonic field value for the vertex.

`value2 : float (bounded) = 1 [min: 0; max: 1]`

> *value for the 2nd point*: Harmonic field value for the vertex.

`colorize : bool = True`

> *Colorize*: Colorize the mesh to provide an indication of the obtained harmonic field.

compute\_scalar\_by\_shape\_diameter\_function\_per\_vertex [](#compute_scalar_by_shape_diameter_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Compute Shape-Diameter Function’

Compute Shape-Diameter Function  
The SDF defines the distance between a point in 3D space and the nearest point on the object's surface.This filter can be used to find out the thickness of the mesh  
Given a face, a set of rays are shot inward, and an average of the distance to hit a face is saved in the face quality. The face quality is then mapped into a color ramp.This filter requires two values:
- the number of rays which will be shot from the barycenter of each face
- the cone amplitude (in degrees) of the cone which we value as valid for the shooting angle
  
**For further details see the reference paper: Shapira Shamir Cohen-Or, Consistent Mesh Partitioning and Skeletonisation using the shaper diameter function, Visual Comput. J. (2008)**  
This filter uses Embree3 library by INTEL.

**Parameters:**

`rays : int = 64`

> *Number of rays*: The number of rays shoot from the barycenter of the face. The higher the number the higher the definition of the SDF but at the cost of the calculation time

`cone_amplitude : float = 90`

> *Cone amplitude* : The value for the angle (in degrees) of the cone for which we consider a ray shooting direction as a valid direction

compute\_scalar\_by\_shape\_diameter\_function\_per\_vertex\_gpu [](#compute_scalar_by_shape_diameter_function_per_vertex_gpu "Link to this definition")

*MeshLab filter name*: ‘Shape Diameter Function’

Calculate the SDF (**shape diameter function**) on the mesh, you can visualize the result colorizing the mesh. The SDF is a scalar function on the mesh surface and represents the neighborhood diameter of the object at each point. Given a point on the mesh surface,several rays are sent inside a cone, centered around the point's inward-normal, to the other side of the mesh. The result is a weighted sum of all rays lengths. For further details, see the reference paper:  
**Shapira Shamir Cohen-Or,  
Consistent Mesh Partitioning and Skeletonisation using the shaper diameter function, Visual Comput. J. (2008)**

**Parameters:**

`onprimitive : str = 'On vertices' (or int = 0)`

> Possible enum values:
> 
> > 0. `'On vertices'`
> > 1. `'On Faces'`
> 
> *Metric:*: Choose whether to trace rays from faces or from vertices.

`numberrays : int = 128`

> *Number of rays:* : The number of rays that will be casted around the normals.

`depthtexturesize : int = 512`

> *Depth texture size*: Size of the depth texture for depth peeling. Higher resolutions provide better sampling of the mesh, with a small performance penalty.

`peelingiteration : int = 10`

> *Peeling Iteration*: Number of depth peeling iteration. Actually is the maximum number of layers that a ray can hit while traversing the mesh. For example, in the case of a sphere, you should specify 2 in this parameter. For a torus, specify 4. **For more complex geometry you should run the depth complexity filter to know the exact value**.

`peelingtolerance : float = 1e-07`

> *Peeling Tolerance*: Depth tolerance used during depth peeling. This is the threshold used to differentiate layers between each others.Two elements whose distance is below this value will be considered as belonging to the same layer.

`coneangle : float = 120`

> *Cone amplitude*: Cone amplitude around normals in degrees. Rays are traced within this cone.

`removefalse : bool = True`

> *Remove false intersections*: For eachray we check the normal at the point of intersection,and ignore intersections where the normal at the intersectionpoints is in the same direction as the point-of-origin(the same direction is defined as an angle difference lessthan 90)

`removeoutliers : bool = False`

> *Remove outliers*: The outliers removal is made on the fly with a supersampling of the depth buffer. For each ray that we trace, we take multiple depth values near the point of intersection and we output only the median of these values. Some mesh can benefit from this additional calculation.

compute\_scalar\_by\_volumetric\_obscurance [](#compute_scalar_by_volumetric_obscurance "Link to this definition")

*MeshLab filter name*: ‘Compute Obscurance’

Compute ambient Obscurance.  
Ambient obscurance is a computer graphics technique used to simulate the effect of global ambient light in a 3D scene, making the mesh appear more realistic.  
This filter requires two values:
- the number of rays(defined by the user), which will be shot from the barycenter of each face in order to compute how many time it is visible from these directions;
- the tau value which represent the T spatial decay;
The resulting values for the obscurance are saved into face quality and mapped on the mesh into a gray shade.  
**For further details see the reference paper: Iones Krupkin Sbert Zhukov Fast, Realistic Lighting for Video Games IEEECG&A 2003**  
This filter uses Embree3 library by INTEL.

**Parameters:**

`rays : int = 64`

> *Number of rays*: The number of rays shoot from the barycenter of the face. The higher the number the higher the definition of the ambient obscurance but at the cost of the calculation time

`tau : float = 0.1`

> *Tau value*: The value to control spatial decay, the higher the value, the grater the influence that the distance (where the ray hits another face) has on the result

compute\_scalar\_by\_volumetric\_obscurance\_gpu [](#compute_scalar_by_volumetric_obscurance_gpu "Link to this definition")

*MeshLab filter name*: ‘Volumetric obscurance’

Calculates obscurance coefficients for the mesh. Obscurance is introduced to avoid the disadvantages of both classical ambient term and ambient occlusion. In ambient occlusion, totally occluded parts of the mesh are black. Instead obscurance, despite still based on a perfectly diffuse light coming from everywhere, accounts for multiple bounces of indirect illumination by means of a function of both the openness of a point and the distance to his occluder (if any). Obscurance is inversely proportional to the number of ray casted from the point that hit an occluder and proportional to the distance a ray travels before hitting the occluder. You can control how much the distance factor influences the final result with the obscurance exponenent (see help below). Obscurance is a value in the range \[0,1\]. For further details see the reference paper:  
**Iones Krupkin Sbert Zhukov  
Fast, Realistic Lighting for Video Games  
IEEECG&A 2003**

**Parameters:**

`onprimitive : str = 'On vertices' (or int = 0)`

> Possible enum values:
> 
> > 0. `'On vertices'`
> > 1. `'On Faces'`
> 
> *Metric:*: Choose whether to trace rays from faces or from vertices.

`numberrays : int = 128`

> *Number of rays:* : The number of rays that will be casted around the normals.

`depthtexturesize : int = 512`

> *Depth texture size*: Size of the depth texture for depth peeling. Higher resolutions provide better sampling of the mesh, with a small performance penalty.

`peelingiteration : int = 10`

> *Peeling Iteration*: Number of depth peeling iteration. Actually is the maximum number of layers that a ray can hit while traversing the mesh. For example, in the case of a sphere, you should specify 2 in this parameter. For a torus, specify 4. **For more complex geometry you should run the depth complexity filter to know the exact value**.

`peelingtolerance : float = 1e-07`

> *Peeling Tolerance*: Depth tolerance used during depth peeling. This is the threshold used to differentiate layers between each others.Two elements whose distance is below this value will be considered as belonging to the same layer.

`coneangle : float = 120`

> *Cone amplitude*: Cone amplitude around normals in degrees. Rays are traced within this cone.

`obscuranceexponent : float = 0.1`

> *Obscurance Exponent*: This parameter controls the spatial decay term in the obscurance formula. The greater the exponent, the greater the influence of distance; that is: even if a ray is blocked by an occluder its contribution to the obscurance term is non zero, but proportional to this parameter. It turs out that if you choose a value of zero, you get the standard ambient occlusion term. **(In this case, only a value of two, in the peeling iteration parameter, has a sense)**

compute\_scalar\_from\_camera\_per\_vertex [](#compute_scalar_from_camera_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Quality from Camera’

Compute vertex quality using the camera definition, according to viewing angle or distance

**Parameters:**

`depth : bool = True`

> *Depth*: Use depth as a factor.

`facing : bool = False`

> *ViewAngle*: Use cosine of viewing angle as a factor.

`clip : bool = False`

> *Clipping*: clip values outside the viewport to zero.

`normalize : bool = False`

> *normalize*: if checked normalize all quality values in range \[0..1\]

`map : bool = False`

> *map into color*: if checked map quality generated values into per-vertex color

compute\_scalar\_from\_raster\_coverage\_per\_face [](#compute_scalar_from_raster_coverage_per_face "Link to this definition")

*MeshLab filter name*: ‘Quality from raster coverage (Face)’

Compute a quality value representing the number of images into which each face of the active mesh is visible.

**Parameters:**

`normalizequality : bool = False`

> *Normalize*: Rescale quality values to the range \[0,1\]

compute\_scalar\_from\_raster\_coverage\_per\_vertex [](#compute_scalar_from_raster_coverage_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Quality from raster coverage (Vertex)’

Compute a quality value representing the number of images into which each vertex of the active mesh is visible.

**Parameters:**

`normalizequality : bool = False`

> *Normalize*: Rescale quality values to the range \[0,1\]

compute\_scalar\_transfer\_face\_to\_vertex [](#compute_scalar_transfer_face_to_vertex "Link to this definition")

*MeshLab filter name*: ‘Transfer Quality: Face to Vertex’

Face to Vertex quality transfer

**Parameters:**

`areaweight : bool = True`

> *Area Weighted*: If true the vertex quality is computed according to the surface of the involved faces.

compute\_scalar\_transfer\_vertex\_to\_face [](#compute_scalar_transfer_vertex_to_face "Link to this definition")

*MeshLab filter name*: ‘Transfer Quality: Vertex to Face’

Vertex to Face quality transfer

compute\_selection\_bad\_faces [](#compute_selection_bad_faces "Link to this definition")

*MeshLab filter name*: ‘Select ‘problematic’ faces’

Select faces with 'problems', like normal inverted w.r.t the surrounding areas, extremely elongated or folded.

**Parameters:**

`usear : bool = True`

> *Select by Aspect Ratio*: if true, faces with aspect ratio below the limit will be selected

`aratio : float (bounded) = 0.02 [min: 0; max: 1]`

> *Aspect Ratio*: Triangle face aspect ratio \[1 (equilateral) - 0 (line)\]: face will be selected if BELOW this threshold

`usenf : bool = False`

> *Select by Normal Angle*: if true, adjacent faces with normals forming an angle above the limit will be selected

`nfratio : float (bounded) = 60 [min: 0; max: 180]`

> *Angle flip*: angle between the adjacent faces: face will be selected if ABOVE this threshold

`select_folded_faces : bool = False`

> *Select folded faces*: If true, folded faces created by the Quadric Edge Collapse decimation will be selected. The face is selected if the angle between the face normal and the normal of the best fitting plane of the neighbor vertices is above the selected threshold.

`folded_faces_angle_threshold : float (bounded) = 160 [min: 90; max: 180]`

> *Folded Faces Angle Threshold*: Angle between the face and the best fitting plane of the neighbours vertices. If it is above the threshold the face is selected.

compute\_selection\_by\_angle\_with\_direction\_per\_face [](#compute_selection_by_angle_with_direction_per_face "Link to this definition")

*MeshLab filter name*: ‘Select Faces by view angle’

Select faces according to the angle between their normal and the view direction. It is used in range map processing to select and delete steep faces parallel to viewdirection.

**Parameters:**

`anglelimit : float (bounded) = 75 [min: 0; max: 180]`

> *angle threshold (deg)*: faces with normal at higher angle w.r.t. the view direction are selected

`usecamera : bool = False`

> *Use ViewPoint from Mesh Camera*: Uses the ViewPoint from the camera associated to the current mesh  
> if there is no camera, an error occurs

`viewpoint : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *ViewPoint*: if UseCamera is true, this value is ignored

compute\_selection\_by\_color\_per\_face [](#compute_selection_by_color_per_face "Link to this definition")

*MeshLab filter name*: ‘Select Faces by Color’

Select part of the mesh based on its color.

**Parameters:**

`color : Color = [0; 0; 0; 255]`

> *Color To Select*: Color that you want to be selected.

`colorspace : str = 'HSV' (or int = 0)`

> Possible enum values:
> 
> > 0. `'HSV'`
> > 1. `'RGB'`
> 
> *Pick Color Space*: The color space that the sliders will manipulate.

`inclusive : bool = True`

> *Inclusive Sel.*: If true only the faces with **all** the vertices within the specified range are selected. Otherwise any face with at least one vertex within the range is selected.

`percentrh : float (bounded) = 0.2 [min: 0; max: 1]`

> *Variation from Red or Hue*: A float between 0 and 1 that represents the percent variation from this color that will be selected. For example if the R was 200 and you put 0.1 then any color with R 200+-25.5 will be selected.

`percentgs : float (bounded) = 0.2 [min: 0; max: 1]`

> *Variation from Green or Saturation*: A float between 0 and 1 that represents the percent variation from this color that will be selected. For example if the R was 200 and you put 0.1 then any color with R 200+-25.5 will be selected.

`percentbv : float (bounded) = 0.2 [min: 0; max: 1]`

> *Variation from Blue or Value*: A float between 0 and 1 that represents the percent variation from this color that will be selected. For example if the R was 200 and you put 0.1 then any color with R 200+-25.5 will be selected.

compute\_selection\_by\_condition\_per\_face [](#compute_selection_by_condition_per_face "Link to this definition")

*MeshLab filter name*: ‘Conditional Face Selection’

Boolean function using muparser lib to perform faces selection over current mesh.  
  
It's possible to use any of the predefined muparser built-in [operators](https://beltoforion.de/en/muparser/features.php#idDef2) and [functions](https://beltoforion.de/en/muparser/features.php#idDef1), like: **&&** (logic and), **||** (logic or), **<**, **<=**, **\>**, **\>=**, **!=** (not equal), **\==** (equal), **\_?\_:\_** (c/c++ ternary operator), and **rnd()** (random value in \[0..1\]), and these values:
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`condselect : str = '(fi == 0)'`

> *boolean function*: type a boolean function that will be evaluated in order to select a subset of faces

compute\_selection\_by\_condition\_per\_vertex [](#compute_selection_by_condition_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Conditional Vertex Selection’

Boolean function using muparser lib to perform vertex selection over current mesh.  
  
It's possible to use any of the predefined muparser built-in [operators](https://beltoforion.de/en/muparser/features.php#idDef2) and [functions](https://beltoforion.de/en/muparser/features.php#idDef1), like: **&&** (logic and), **||** (logic or), **<**, **<=**, **\>**, **\>=**, **!=** (not equal), **\==** (equal), **\_?\_:\_** (c/c++ ternary operator), and **rnd()** (random value in \[0..1\]), and these values:
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`condselect : str = '(q < 0)'`

> *boolean function*: type a boolean function that will be evaluated in order to select a subset of vertices  
> example: (y > 0) and (ny > 0)

compute\_selection\_by\_edge\_length [](#compute_selection_by_edge_length "Link to this definition")

*MeshLab filter name*: ‘Select Faces with edges longer than…’

Select all triangles having an edge with length greater or equal than a given threshold.

**Parameters:**

`threshold : float (bounded) = 0.00866025 [min: 0; max: 0.866025]`

> *Edge Threshold*: All the faces with an edge **longer** than this threshold will be deleted. Useful for removing long skinny faces obtained by bad triangulation of range maps.

compute\_selection\_by\_non\_manifold\_edges\_per\_face [](#compute_selection_by_non_manifold_edges_per_face "Link to this definition")

*MeshLab filter name*: ‘Select non Manifold Edges’

Select the faces and the vertices incident on non manifold edges (e.g. edges where more than two faces are incident); note that this function select the components that are related to non manifold edges. The case of non manifold vertices is specifically managed by the pertinent filter.

compute\_selection\_by\_non\_manifold\_per\_vertex [](#compute_selection_by_non_manifold_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Select non Manifold Vertices’

Select the non manifold vertices that do not belong to non manifold edges. For example two cones connected by their apex. Vertices incident on non manifold edges are ignored.

compute\_selection\_by\_scalar\_per\_face [](#compute_selection_by_scalar_per_face "Link to this definition")

*MeshLab filter name*: ‘Select by Face Quality’

Select all the faces/vertices with within the specified face quality range.

**Parameters:**

`minq : float (bounded) = 0 [min: 0; max: 0]`

> *Min Quality*: Minimum acceptable quality value

`maxq : float (bounded) = 0 [min: 0; max: 0]`

> *Max Quality*: Maximum acceptable quality value

`inclusive : bool = True`

> *Inclusive Sel.*: If true only the vertices with **all** the adjacent faces within the specified range are selected. Otherwise any vertex with at least one face within the range is selected.

compute\_selection\_by\_scalar\_per\_vertex [](#compute_selection_by_scalar_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Select by Vertex Quality’

Select all the faces/vertices within the specified vertex quality range.

**Parameters:**

`minq : float (bounded) = 0 [min: 0; max: 0]`

> *Min Quality*: Minimum acceptable quality value

`maxq : float (bounded) = 0 [min: 0; max: 0]`

> *Max Quality*: Maximum acceptable quality value

`inclusive : bool = True`

> *Inclusive Face Sel.*: If true only the faces with **all** the vertices within the specified range are selected. Otherwise any face with at least one vertex within the range is selected.

compute\_selection\_by\_self\_intersections\_per\_face [](#compute_selection_by_self_intersections_per_face "Link to this definition")

*MeshLab filter name*: ‘Select Self Intersecting Faces’

Select only self intersecting faces.

compute\_selection\_by\_small\_disconnected\_components\_per\_face [](#compute_selection_by_small_disconnected_components_per_face "Link to this definition")

*MeshLab filter name*: ‘Select small disconnected component’

Select the small disconnected components of a mesh.

**Parameters:**

`nbfaceratio : float = 0.1`

> *Small component ratio*: This ratio (between 0 and 1) defines the meaning of *small* as the threshold ratio between the number of facesof the largest component and the other ones. A larger value will select more components.

`nonclosedonly : bool = False`

> *Select only non closed components*:

`nbneighbors : int = 16`

> *Number of neighbors*: Number of neighbors used to estimate the local density. Larger values lead to smoother variations.

compute\_selection\_by\_texture\_seams\_per\_vertex [](#compute_selection_by_texture_seams_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Select Vertex Texture Seams’

Colorize only border edges.

compute\_selection\_crease\_per\_edge [](#compute_selection_crease_per_edge "Link to this definition")

*MeshLab filter name*: ‘Select Crease Edges’

It select the crease edges of a mesh according to edge dihedral angle.  
Angle between face normal is considered signed according to convexity/concavity.Convex angles are positive and concave are negative.

**Parameters:**

`angledegneg : float = -45`

> *Concave Angle Thr. (deg)*: Concave Dihedral Angle threshold for considering an edge a crease. If the normals between two faces forms an concave diheadral angle smaller than the threshold the edge is considered a crease.

`angledegpos : float = 45`

> *Convex Angle Thr. (deg)*: The angle threshold for considering an edge a crease. If the normals between two faces forms an angle larger than the threshold the edge is considered a crease.

compute\_selection\_from\_mesh\_border [](#compute_selection_from_mesh_border "Link to this definition")

*MeshLab filter name*: ‘Select Border’

Select vertices and faces on the boundary.

compute\_selection\_of\_visible\_convex\_hull\_per\_vertex [](#compute_selection_of_visible_convex_hull_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Select Convex Hull Visible Points’

Select the **visible points** in the convex hull of a point cloud, as viewed from a given viewpoint.  
It uses the Qhull library (http://www.qhull.org/  
  
The algorithm used (Katz, Tal and Basri 2007) determines visibility without reconstructing a surface or estimating normals.A point is considered visible if its transformed point lies on the convex hull of a transformed points cloud from the original mesh points.

**Parameters:**

`radiusthreshold : float (bounded) = 0 [min: 0; max: 7]`

> *radius threshold* : Bounds the radius of the sphere used to select visible points.It is used to adjust the radius of the sphere (calculated as distance between the center and the farthest point from it) according to the following equation:  
> radius = radius \* pow(10,threshold);  
> As the radius increases more points are marked as visible.Use a big threshold for dense point clouds, a small one for sparse clouds.

`usecamera : bool = False`

> *Use ViewPoint from Mesh Camera*: Uses the ViewPoint from the camera associated to the current mesh  
> if there is no camera, an error occurs

`viewpoint : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *ViewPoint*: if UseCamera is true, this value is ignored

`convex_hullfp : bool = False`

> *Show Partial Convex Hull of flipped points*: Show Partial Convex Hull of the transformed point cloud

`triangvp : bool = False`

> *Show a triangulation of the visible points*: Show a triangulation of the visible points

compute\_selection\_point\_cloud\_outliers [](#compute_selection_point_cloud_outliers "Link to this definition")

*MeshLab filter name*: ‘Select Outliers’

Select the vertex classified as outlier using Local Outlier Propabilty measure described in:  
**'LoOP: Local Outlier Probabilities'** Kriegel et al.  
CIKM 2009

**Parameters:**

`propthreshold : float (bounded) = 0.8 [min: 0; max: 1]`

> *Probability*: Threshold to select the vertex. The vertex is selected if the LoOP value is above the threshold.

`knearest : int = 32`

> *Number of neighbors*: Number of neighbours used to compute the LoOP

compute\_selection\_transfer\_face\_to\_vertex [](#compute_selection_transfer_face_to_vertex "Link to this definition")

*MeshLab filter name*: ‘Select Vertices from Faces’

Select vertices from selected faces.

**Parameters:**

`inclusive : bool = True`

> *Strict Selection*: If true only the vertices with **all** the incident face selected are selected. Otherwise any vertex with at least one incident selected face will be selected.

compute\_selection\_transfer\_vertex\_to\_face [](#compute_selection_transfer_vertex_to_face "Link to this definition")

*MeshLab filter name*: ‘Select Faces from Vertices’

Select faces from selected vertices.

**Parameters:**

`inclusive : bool = True`

> *Strict Selection*: If true only the faces with **all** selected vertices are selected. Otherwise any face with at least one selected vertex will be selected.

compute\_texcoord\_by\_function\_per\_vertex [](#compute_texcoord_by_function_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Texture Function’

Texture function using muparser to generate new texture coords for every vertex  
- Per-vertex variables:  
	**x,y,z** (position), **nx,ny,nz** (normal), **r,g,b,a** (color), **q** (quality), **vi** (vertex index), **vtu,vtv,ti** (texture coords and texture index), **vsel** ( 1 if selected, 0 if not selected).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length)
- User-defined attributes:  
	All user defined custom *vertex attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`u : str = 'x'`

> *func u =* : function to generate u texture coord. Expected Range 0-1

`v : str = 'y'`

> *func v =* : function to generate v texture coord. Expected Range 0-1

`onselected : bool = False`

> *only on selection*: if checked, only affects selected vertices

compute\_texcoord\_by\_function\_per\_wedge [](#compute_texcoord_by_function_per_wedge "Link to this definition")

*MeshLab filter name*: ‘Per Wedge Texture Function’

Texture function using muparser to generate new per wedge tex coords for every face  
Insert six functions each u v for each one of the three vertex of a face  
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`u0 : str = 'x0'`

> *func u0 =* : function to generate u texture coord. of wedge 0. Expected Range 0-1

`v0 : str = 'y0'`

> *func v0 =* : function to generate v texture coord. of wedge 0. Expected Range 0-1

`u1 : str = 'x1'`

> *func u1 =* : function to generate u texture coord. of wedge 1. Expected Range 0-1

`v1 : str = 'y1'`

> *func v1 =* : function to generate v texture coord. of wedge 1. Expected Range 0-1

`u2 : str = 'x2'`

> *func u2 =* : function to generate u texture coord. of wedge 2. Expected Range 0-1

`v2 : str = 'y2'`

> *func v2 =* : function to generate v texture coord. of wedge 2. Expected Range 0-1

`onselected : bool = False`

> *only on selection*: if checked, only affects selected faces

*MeshLab filter name*: ‘Parameterization + texturing from registered rasters’

The mesh is parameterized and textured by creating some patches that correspond to projection of portions of surfaces onto the set of registered rasters.

**Parameters:**

`texturesize : int = 1024`

> *Texture size*: Specifies the dimension of the generated texture

`texturename : str = 'texture.png'`

> *Texture name*: Specifies the name of the file into which the texture image will be saved

`colorcorrection : bool = True`

> *Color correction*: If true, the final texture is corrected so as to ensure seamless transitions

`colorcorrectionfiltersize : int = 1`

> *Color correction filter*: It is the radius (in pixel) of the kernel that is used to compute the difference between corresponding texels in different rasters. Default is 1 that generate a 3x3 kernel. Highest values increase the robustness of the color correction process in the case of strong image-to-geometry misalignments

`usedistanceweight : bool = True`

> *Use distance weight*: Includes a weight accounting for the distance to the camera during the computation of reference images

`useimgborderweight : bool = True`

> *Use image border weight*: Includes a weight accounting for the distance to the image border during the computation of reference images

`usealphaweight : bool = False`

> *Use image alpha weight*: If true, alpha channel of the image is used as additional weight. In this way it is possible to mask-out parts of the images that should not be projected on the mesh. Please note this is not a transparency effect, but just influences the weigthing between different images

`cleanisolatedtriangles : bool = True`

> *Clean isolated triangles*: Remove all patches compound of a single triangle by aggregating them to adjacent patches

`stretchingallowed : bool = False`

> *UV stretching*: If true, texture coordinates are stretched so as to cover the full interval \[0,1\] for both directions

`texturegutter : int = 4`

> *Texture gutter*: Extra boundary to add to each patch before packing in texture space (in pixels)

compute\_texcoord\_parametrization\_flat\_plane\_per\_wedge [](#compute_texcoord_parametrization_flat_plane_per_wedge "Link to this definition")

*MeshLab filter name*: ‘Parametrization: Flat Plane’

Builds a trivial flat-plane parametrization.

**Parameters:**

`projectionplane : str = 'XY' (or int = 0)`

> Possible enum values:
> 
> > 0. `'XY'`
> > 1. `'XZ'`
> > 2. `'YZ'`
> 
> *Projection plane*: Choose the projection plane

`aspectratio : bool = False`

> *Preserve Ratio*: If checked the resulting parametrization will preserve the original apsect ratio of the model otherwise it will fill up the whole 0..1 uv space

`sidegutter : float = 0`

> *Side Gutter*: Leave an empty space around the parametrization area of the specified size (in texture space); accepted range \[0.0 - 0.5\].

*MeshLab filter name*: ‘Parameterization from registered rasters’

The mesh is parameterized by creating some patches that correspond to projection of portions of surfaces onto the set of registered rasters.

**Parameters:**

`usedistanceweight : bool = True`

> *Use distance weight*: Includes a weight accounting for the distance to the camera during the computation of reference images

`useimgborderweight : bool = True`

> *Use image border weight*: Includes a weight accounting for the distance to the image border during the computation of reference images

`usealphaweight : bool = False`

> *Use image alpha weight*: If true, alpha channel of the image is used as additional weight. In this way it is possible to mask-out parts of the images that should not be projected on the mesh. Please note this is not a transparency effect, but just influences the weigthing between different images

`cleanisolatedtriangles : bool = True`

> *Clean isolated triangles*: Remove all patches compound of a single triangle by aggregating them to adjacent patches

`stretchingallowed : bool = False`

> *UV stretching*: If true, texture coordinates are stretched so as to cover the full interval \[0,1\] for both directions

`texturegutter : int = 4`

> *Texture gutter*: Extra boundary to add to each patch before packing in texture space (in pixels)

compute\_texcoord\_parametrization\_harmonic [](#compute_texcoord_parametrization_harmonic "Link to this definition")

*MeshLab filter name*: ‘Harmonic Parametrization’

Computes a single patch, fixed boundary harmonic parametrization of a mesh. The filter requires that the input mesh has a single fixed boundary.The resulting parametrization is saved in the per vertex texture coordinates.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).  

**Parameters:**

`harm_function : int = 1`

> *N-Harmonic Function*: 1 denotes harmonic function, 2 biharmonic, 3 triharmonic, etc.

compute\_texcoord\_parametrization\_least\_squares\_conformal\_maps [](#compute_texcoord_parametrization_least_squares_conformal_maps "Link to this definition")

*MeshLab filter name*: ‘Least Squares Conformal Maps Parametrization’

Compuites a least squares conformal maps parametrization of a mesh. The resulting parametrization is saved in the per vertex texture coordinates.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).

compute\_texcoord\_parametrization\_triangle\_trivial\_per\_wedge [](#compute_texcoord_parametrization_triangle_trivial_per_wedge "Link to this definition")

*MeshLab filter name*: ‘Parametrization: Trivial Per-Triangle’

Builds a trivial triangle-by-triangle parametrization.  
Two methods are provided, the first maps all triangles into equal sized triangles, while the second one adapt the size of the triangles in texture space to their original size.

**Parameters:**

`sidedim : int = 0`

> *Quads per line*: Indicates how many triangles have to be put on each line (every quad contains two triangles)  
> Leave 0 for automatic calculation

`textdim : int = 1024`

> *Texture Dimension (px)*: Gives an indication on how big the texture is

`border : int = 2`

> *Inter-Triangle border (px)*: Specifies how many pixels to be left between triangles in parametrization domain

`method : str = 'Space-optimizing' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Basic'`
> > 1. `'Space-optimizing'`
> 
> *Method*: Choose space optimizing to map smaller faces into smaller triangles in parametrizazion domain

compute\_texcoord\_transfer\_vertex\_to\_wedge [](#compute_texcoord_transfer_vertex_to_wedge "Link to this definition")

*MeshLab filter name*: ‘Convert PerVertex UV into PerWedge UV’

Converts per Vertex Texture Coordinates to per Wedge Texture Coordinates. It does not merge superfluous vertices...

compute\_texcoord\_transfer\_wedge\_to\_vertex [](#compute_texcoord_transfer_wedge_to_vertex "Link to this definition")

*MeshLab filter name*: ‘Convert PerWedge UV into PerVertex UV’

Converts per Wedge Texture Coordinates to per Vertex Texture Coordinates splitting vertices with not coherent Wedge coordinates.

compute\_texmap\_from\_color [](#compute_texmap_from_color "Link to this definition")

*MeshLab filter name*: ‘Transfer: Vertex Color to Texture’

Fills the specified texture using per-vertex color data of the mesh.

**Parameters:**

`textname : str = ''`

> *Texture name*: The name of the texture to be created

`textw : int = 1024`

> *Texture width (px)*: The texture width

`texth : int = 1024`

> *Texture height (px)*: The texture height

`overwrite : bool = False`

> *Overwrite texture*: if current mesh has a texture will be overwritten (with provided texture dimension)

`pullpush : bool = True`

> *Fill texture*: if enabled the unmapped texture space is colored using a pull push filling algorithm, if false is set to black

create\_annulus [](#create_annulus "Link to this definition")

*MeshLab filter name*: ‘Annulus’

Create an Annulus e.g. a flat region bounded by two concentric circles, or a holed disk.

**Parameters:**

`internalradius : float = 0.5`

> *Internal Radius*: Internal Radius of the annulus

`externalradius : float = 1`

> *External Radius*: Externale Radius of the annulus

`sides : int = 32`

> *Sides*: Number of the sides of the poligonal approximation of the annulus

create\_cone [](#create_cone "Link to this definition")

*MeshLab filter name*: ‘Cone’

Create a Cone

**Parameters:**

`r0 : float = 1`

> *Radius 1*: Radius of the bottom circumference

`r1 : float = 2`

> *Radius 2*: Radius of the top circumference

`h : float = 3`

> *Height*: Height of the Cone

`subdiv : int = 36`

> *Side*: Number of sides of the polygonal approximation of the cone

create\_cube [](#create_cube "Link to this definition")

*MeshLab filter name*: ‘Box/Cube’

Create a Box, Cube, Hexahedron. You can specify the side length.

**Parameters:**

`size : float = 1`

> *Scale factor*: Scales the new mesh

create\_dodecahedron [](#create_dodecahedron "Link to this definition")

*MeshLab filter name*: ‘Dodecahedron’

Create an Dodecahedron

create\_fractal\_terrain [](#create_fractal_terrain "Link to this definition")

*MeshLab filter name*: ‘Fractal Terrain’

Generates a fractal terrain perturbation with five different algorithms.  
Some good parameter values to start with are:  

| \- | Seed | Octaves | Lacunarity | Fractal increment | Offset | Gain |
| --- | --- | --- | --- | --- | --- | --- |
| fBM | 1 | 10 | 2 | 1.2 | \- | \- |
| Standard multifractal | 1 | 8 | 2 | 0.9 | 0.9 | \- |
| Heterogeneous multifractal | 1 | 8 | 3 | 0.9 | 0.4 | \- |
| Hybrid multifractal | 1 | 8 | 4 | 0.1 | 0.3 | \- |
| Ridged multifractal | 2 | 8 | 4 | 0.5 | 0.9 | 2 |

  
  
Detailed algorithms descriptions can be found in:  
*Ebert, D.S., Musgrave, F.K., Peachey, D., Perlin, K., and Worley, S.*  
**Texturing and Modeling: A Procedural Approach**  
Morgan Kaufmann Publishers Inc., San Francisco, CA, USA, 2002.  

**Parameters:**

`steps : int = 8`

> *Subdivision steps:*: Defines the detail of the generated terrain. Allowed values are in range \[2,9\]. Use values from 6 to 9 to obtain reasonable results.

`maxheight : float (bounded) = 0.2 [min: 0; max: 1]`

> *Max height:*: Defines the maximum perturbation height as a fraction of the terrain's side.

`scale : float (bounded) = 1 [min: 0; max: 10]`

> *Scale factor:*: Scales the fractal perturbation in and out. Values larger than 1 mean zoom out; values smaller than one mean zoom in.

`seed : float = 2`

> *Seed:*: By varying this seed, the terrain morphology will change.  
> Don't change the seed if you want to refine the current terrain morphology by changing the other parameters.

`algorithm : str = 'Ridged multifractal terrain' (or int = 4)`

> Possible enum values:
> 
> > 0. `'fBM (fractal Brownian Motion)'`
> > 1. `'Standard multifractal'`
> > 2. `'Heterogeneous multifractal'`
> > 3. `'Hybrid multifractal terrain'`
> > 4. `'Ridged multifractal terrain'`
> 
> *Algorithm*: The algorithm with which the fractal terrain will be generated.

`octaves : float (bounded) = 8 [min: 1; max: 20]`

> *Octaves:*: The number of Perlin noise frequencies that will be used to generate the terrain. Reasonable values are in range \[2,9\].

`lacunarity : float = 4`

> *Lacunarity:*: The gap between noise frequencies. This parameter is used in conjunction with fractal increment to compute the spectral weights that contribute to the noise in each octave.

`fractalincrement : float = 0.5`

> *Fractal increment:*: This parameter defines how rough the generated terrain will be. The range of reasonable values changes according to the used algorithm, however you can choose it in range \[0.2, 1.5\].

`offset : float = 0.9`

> *Offset:*: This parameter controls the multifractality of the generated terrain. If offset is low, then the terrain will be smooth.

`gain : float = 2.5`

> *Gain:*: Ignored in all the algorithms except the ridged one. This parameter defines how hard the terrain will be.

`saveasquality : bool = False`

> *Save as vertex quality*: Saves the perturbation value as vertex quality.

create\_grid [](#create_grid "Link to this definition")

*MeshLab filter name*: ‘Grid Generator’

Generate a new 2D Grid mesh with number of vertices on X and Y axis specified by user with absolute length/height.  
It's possible to center Grid on origin.

**Parameters:**

`numvertx : int = 10`

> *num vertices on x*: number of vertices on x. it must be positive

`numverty : int = 10`

> *num vertices on y*: number of vertices on y. it must be positive

`absscalex : float = 0.3`

> *x scale*: absolute scale on x (float)

`absscaley : float = 0.3`

> *y scale*: absolute scale on y (float)

`center : bool = False`

> *centered on origin*: center grid generated by filter on origin.  
> Grid is first generated and than moved into origin (using muparser lib to perform fast calc on every vertex)

create\_icosahedron [](#create_icosahedron "Link to this definition")

*MeshLab filter name*: ‘Icosahedron’

Create an Icosahedron

create\_implicit\_surface [](#create_implicit_surface "Link to this definition")

*MeshLab filter name*: ‘Implicit Surface’

Generate a new mesh that corresponds to the 0 valued isosurface defined by the scalar field generated by the given expression

**Parameters:**

`voxelsize : float = 0.05`

> *Size of Voxel*: Size of the voxel that is used by for the grid where the field is sampled. Smaller this value, higher precision, but higher processing times.

`minx : float = -1`

> *Min X*: Range where the field is sampled

`miny : float = -1`

> *Min Y*: Range where the field is sampled

`minz : float = -1`

> *Min Z*: Range where the field is sampled

`maxx : float = 1`

> *Max X*: Range where the field is sampled

`maxy : float = 1`

> *Max Y*: Range where the field is sampled

`maxz : float = 1`

> *Max Z*: Range where the field is sampled

`expr : str = 'x*x+y*y+z*z-0.5'`

> *Function =*: This expression is evaluated for each voxel of the grid. The surface passing through the zero valued points of this field is then extracted using marching cube.

create\_mesh\_by\_grammar [](#create_mesh_by_grammar "Link to this definition")

*MeshLab filter name*: ‘Structure Synth Mesh Creation’

Structure Synth mesh creation based on Eisen Script.  
For further instruction visit http://structuresynth.sourceforge.net/reference.php

**Parameters:**

`grammar : str = 'set maxdepth 40 R1 R2 rule R1 { { x 1 rz 6 ry 6 s 0.99 } R1 { s 2 } sphere } rule R2 {{ x -1 rz 6 ry 6 s 0.99 } R2 { s 2 } sphere} '`

> *Eisen Script grammar*: Write a grammar according to Eisen Script specification and using the primitives box, sphere, mesh, dot and triangle

`seed : int = 1`

> *seed for random construction*: Seed needed to build the mesh

`sphereres : int = 1`

> *set maximum resolution of sphere primitives, it must be included between 1 and 4*: increasing the resolution of the spheres will improve the quality of the mesh

create\_noisy\_isosurface [](#create_noisy_isosurface "Link to this definition")

*MeshLab filter name*: ‘Noisy Isosurface’

Create a isosurface perturbed by a noisy isosurface.

**Parameters:**

`resolution : int = 64`

> *Grid Resolution*: Resolution of the side of the cubic grid used for the volume creation

create\_octahedron [](#create_octahedron "Link to this definition")

*MeshLab filter name*: ‘Octahedron’

Create an Octahedron

create\_sphere [](#create_sphere "Link to this definition")

*MeshLab filter name*: ‘Sphere’

Create a Sphere, whose topology is obtained as regular subdivision of an icosahedron.

**Parameters:**

`radius : float = 1`

> *Radius*: Radius of the sphere

`subdiv : int = 3`

> *Subdiv. Level*: Number of the recursive subdivision of the surface. Default is 3 (a sphere approximation composed by 1280 faces).  
> Admitted values are in the range 0 (an icosahedron) to 8 (a 1.3 MegaTris approximation of a sphere)

create\_sphere\_cap [](#create_sphere_cap "Link to this definition")

*MeshLab filter name*: ‘Sphere Cap’

Create a Sphere Cap, or spherical dome, subtended by a cone of given angle

**Parameters:**

`angle : float = 60`

> *Angle*: Angle of the cone subtending the cap. It must be < 180

`subdiv : int = 3`

> *Subdiv. Level*: Number of the recursive subdivision of the surface. Default is 3 (a sphere approximation composed by 1280 faces).  
> Admitted values are in the range 0 (an icosahedron) to 8 (a 1.3 MegaTris approximation of a sphere)

create\_sphere\_points [](#create_sphere_points "Link to this definition")

*MeshLab filter name*: ‘Points on a Sphere’

Create a spherical point cloud, it can be random or regularly distributed.

**Parameters:**

`pointnum : int = 100`

> *Point Num*: Number of points (approximate).

`spheregentech : str = 'Octahedron' (or int = 3)`

> Possible enum values:
> 
> > 0. `'Montecarlo'`
> > 1. `'Poisson Sampling'`
> > 2. `'DiscoBall'`
> > 3. `'Octahedron'`
> > 4. `'Fibonacci'`
> 
> *Generation Technique:*: Generation Technique:**Montecarlo**: The points are randomly generated with an uniform distribution.  
> **Poisson Disk**: The points are to follow a poisson disk distribution.  
> **Disco Ball** Dave Rusin's disco ball algorithm for the regular placement of points on a sphere is used.  
> **Recursive Octahedron** Points are generated on the vertex of a recursively subdivided octahedron  
> **Fibonacci**.

create\_tetrahedron [](#create_tetrahedron "Link to this definition")

*MeshLab filter name*: ‘Tetrahedron’

Create a Tetrahedron

create\_torus [](#create_torus "Link to this definition")

*MeshLab filter name*: ‘Torus’

Create a Torus

**Parameters:**

`hradius : float = 3`

> *Horizontal Radius*: Radius of the whole horizontal ring of the torus

`vradius : float = 1`

> *Vertical Radius*: Radius of the vertical section of the ring

`hsubdiv : int = 24`

> *Horizontal Subdivision*: Subdivision step of the ring

`vsubdiv : int = 12`

> *Vertical Subdivision*: Number of sides of the polygonal approximation of the torus section

delete\_current\_mesh [](#delete_current_mesh "Link to this definition")

*MeshLab filter name*: ‘Delete Current Mesh’

The current mesh layer is deleted

delete\_current\_raster [](#delete_current_raster "Link to this definition")

*MeshLab filter name*: ‘Delete Current Raster’

The current raster layer is deleted

delete\_non\_active\_rasters [](#delete_non_active_rasters "Link to this definition")

*MeshLab filter name*: ‘Delete all Non Selected Rasters’

All non selected raster layers are deleted

delete\_non\_visible\_meshes [](#delete_non_visible_meshes "Link to this definition")

*MeshLab filter name*: ‘Delete all non visible Mesh Layers’

All the non visible mesh layers are deleted

export\_mesh\_to\_sketchfab [](#export_mesh_to_sketchfab "Link to this definition")

*MeshLab filter name*: ‘Export to Sketchfab’

Upload the current layer on Sketchfab. It requires that you have an account and that you set your private API token in the preferences of MeshLab.

**Parameters:**

`sketchfabkeycode : str = '00000000'`

> *SketchFab Account API token*: The API token of the account on which to upload the model.  
> You can find it by going on Settings -> Password and API -> API token.

`title : str = 'MeshLabModel'`

> *Title*: Mandatory.

`description : str = 'A model generated with meshlab'`

> *Description*: Mandatory. A short description of the model that is uploaded.

`tags : str = 'meshlab'`

> *Tags*: Mandatory. Tags must be separated by a space. Typical tags usually used by MeshLab users: scan, photogrammetry.

`isprivate : bool = False`

> *Private*: This parameter can be true only for PRO account.

`ispublished : bool = False`

> *Publish*: If true the model will be published immediately.

`autorotate : bool = True`

> *Auto Rotate*: If true the model rotated by 90 degree on the X axis to maintain similar default orientation.

`saveapisetting : bool = False`

> *Save SketchFab Code*: Saves the API SketchFab code into the MeshLab settings, allowing to load it as default value every time you run this filter.

generate\_alpha\_shape [](#generate_alpha_shape "Link to this definition")

*MeshLab filter name*: ‘Alpha Complex/Shape’

Calculate the **Alpha Shape** of the mesh(Edelsbrunner and P.Mucke 1994) with Qhull library (http://www.qhull.org/).  
  
From a given finite point set in the space it computes 'the shape' of the set.The Alpha Shape is the boundary of the alpha complex, that is a subcomplex of the Delaunay triangulation of the given point set.  
For a given value of 'alpha', the alpha complex includes all the simplices in the Delaunay triangulation which have an empty circumsphere with radius equal or smaller than 'alpha'.  
The filter inserts the minimum value of alpha (the circumradius of the triangle) in attribute Quality foreach face.

**Parameters:**

`alpha : PercentageValue = 1%`

> *Alpha value*: Compute the alpha value as percentage of the diagonal of the bbox

`filtering : str = 'Alpha Complex' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Alpha Complex'`
> > 1. `'Alpha Shape'`
> 
> *Get:*: Select the output. The Alpha Shape is the boundary of the Alpha Complex

generate\_alpha\_wrap [](#generate_alpha_wrap "Link to this definition")

*MeshLab filter name*: ‘Alpha Wrap’

This filter extecutes an Alpha Wrap based on the input mesh.  
The filter uses the original code provided in CGAL [3D Alpha Wrapping](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#Chapter_3D_Alpha_wrapping).  
  
Alpha: this is the size of the 'ball', specified as the fraction of the length of the largest diagonal of the bounding box. So, if this value is 0.02 then the size of the ball is 2% of the largest diagonal. Note that the run-time and memory consumption will increase with a smaller ball size.  
  
Offset: the offset distance that is added to the surface, always larger than 0, as a fraction of the length of the largest diagonal. A value of 0.001 means that the surface will be offset by a thousandth of this length.  
  
The implementation is based on the following paper:  
Cédric Portaneri, Mael Rouxel-Labbé, Michael Hemmer, David Cohen-Steiner, Pierre Alliez, [**"Alpha Wrapping with an Offset"**](https://inria.hal.science/hal-03688637) (2022)  
  
This plugin is contributed by Lex van der Sluijs at PTC.  

**Parameters:**

`alpha_fraction : float = 0.02`

> *Alpha: the size of the ball (fraction)*:

`offset_fraction : float = 0.001`

> *Offset added to the surface (fraction)*:

generate\_boolean\_difference [](#generate_boolean_difference "Link to this definition")

*MeshLab filter name*: ‘Mesh Boolean: Difference’

This filter extecutes an exact boolean difference between two meshes.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).  
The implementation refers to the following paper:  
*Qingnan Zhou, Eitan Grinspun, Denis Zorin, Alec Jacobson*,  
**"Mesh Arrangements for Solid Geometry"**  

**Parameters:**

`first_mesh : int = 0`

> *First Mesh*: The first operand of the boolean operation

`second_mesh : int = 0`

> *Second Mesh*: The second operand of the boolean operation

`transfer_face_color : bool = False`

> *Transfer face color*: Save the color of the birth face to the faces of resulting mesh.

`transfer_face_quality : bool = False`

> *Transfer face quality*: Save the quality of the birth face to the faces of resulting mesh.

`transfer_vert_color : bool = False`

> *Transfer vertex color*: Save the color of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

`transfer_vert_quality : bool = False`

> *Transfer vertex quality*: Save the quality of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

generate\_boolean\_intersection [](#generate_boolean_intersection "Link to this definition")

*MeshLab filter name*: ‘Mesh Boolean: Intersection’

This filter extecutes an exact boolean intersection between two meshes.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).  
The implementation refers to the following paper:  
*Qingnan Zhou, Eitan Grinspun, Denis Zorin, Alec Jacobson*,  
**"Mesh Arrangements for Solid Geometry"**  

**Parameters:**

`first_mesh : int = 0`

> *First Mesh*: The first operand of the boolean operation

`second_mesh : int = 0`

> *Second Mesh*: The second operand of the boolean operation

`transfer_face_color : bool = False`

> *Transfer face color*: Save the color of the birth face to the faces of resulting mesh.

`transfer_face_quality : bool = False`

> *Transfer face quality*: Save the quality of the birth face to the faces of resulting mesh.

`transfer_vert_color : bool = False`

> *Transfer vertex color*: Save the color of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

`transfer_vert_quality : bool = False`

> *Transfer vertex quality*: Save the quality of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

generate\_boolean\_union [](#generate_boolean_union "Link to this definition")

*MeshLab filter name*: ‘Mesh Boolean: Union’

This filter extecutes an exact boolean union between two meshes.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).  
The implementation refers to the following paper:  
*Qingnan Zhou, Eitan Grinspun, Denis Zorin, Alec Jacobson*,  
**"Mesh Arrangements for Solid Geometry"**  

**Parameters:**

`first_mesh : int = 0`

> *First Mesh*: The first operand of the boolean operation

`second_mesh : int = 0`

> *Second Mesh*: The second operand of the boolean operation

`transfer_face_color : bool = False`

> *Transfer face color*: Save the color of the birth face to the faces of resulting mesh.

`transfer_face_quality : bool = False`

> *Transfer face quality*: Save the quality of the birth face to the faces of resulting mesh.

`transfer_vert_color : bool = False`

> *Transfer vertex color*: Save the color of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

`transfer_vert_quality : bool = False`

> *Transfer vertex quality*: Save the quality of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

generate\_boolean\_xor [](#generate_boolean_xor "Link to this definition")

*MeshLab filter name*: ‘Mesh Boolean: Symmetric Difference (XOR)’

This filter extecutes an exact boolean symmetric difference (XOR) between two meshes.  
The filter uses the original code provided in the [libigl library](https://libigl.github.io/).  
The implementation refers to the following paper:  
*Qingnan Zhou, Eitan Grinspun, Denis Zorin, Alec Jacobson*,  
**"Mesh Arrangements for Solid Geometry"**  

**Parameters:**

`first_mesh : int = 0`

> *First Mesh*: The first operand of the boolean operation

`second_mesh : int = 0`

> *Second Mesh*: The second operand of the boolean operation

`transfer_face_color : bool = False`

> *Transfer face color*: Save the color of the birth face to the faces of resulting mesh.

`transfer_face_quality : bool = False`

> *Transfer face quality*: Save the quality of the birth face to the faces of resulting mesh.

`transfer_vert_color : bool = False`

> *Transfer vertex color*: Save the color of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

`transfer_vert_quality : bool = False`

> *Transfer vertex quality*: Save the quality of the birth vertex to the faces of resulting mesh. For newly created vertices, a simple average of the neighbours is computed.

generate\_by\_merging\_visible\_meshes [](#generate_by_merging_visible_meshes "Link to this definition")

*MeshLab filter name*: ‘Flatten Visible Layers’

Flatten all or only the visible layers into a single new mesh.  
Transformations are preserved. Existing layers can be optionally deleted

**Parameters:**

`mergevisible : bool = True`

> *Merge Only Visible Layers*: If true, flatten only visible layers, otherwise, all layers are used.

`deletelayer : bool = True`

> *Delete Layers* : Delete all the layers used as source in flattening.  
> If all layers are visible only a single layer will remain after the invocation of this filter.

`mergevertices : bool = True`

> *Merge duplicate vertices*: Merge the vertices that are duplicated among different layers.  
>   
> Very useful when the layers are spliced portions of a single big mesh.

`alsounreferenced : bool = True`

> *Keep unreferenced vertices*: Do not discard unreferenced vertices from source layers  
>   
> Necessary for point-cloud layers.

generate\_convex\_hull [](#generate_convex_hull "Link to this definition")

*MeshLab filter name*: ‘Convex Hull’

Calculate the **convex hull** with Qhull library (http://www.qhull.org/html/qconvex.htm).  
  
The convex hull of a set of points is the boundary of the minimal convex set containing the given non-empty finite set of points.

generate\_copy\_of\_current\_mesh [](#generate_copy_of_current_mesh "Link to this definition")

*MeshLab filter name*: ‘Duplicate Current layer’

Create a new layer containing the same model as the current one

generate\_cylindrical\_unwrapping [](#generate_cylindrical_unwrapping "Link to this definition")

*MeshLab filter name*: ‘Geometric Cylindrical Unwrapping’

Unwrap the geometry of current mesh along a clylindrical equatorial projection. The cylindrical projection axis is centered on the origin and directed along the vertical **Y** axis.

**Parameters:**

`startangle : float = 0`

> *Start angle (deg)*: The starting angle of the unrolling process.

`endangle : float = 360`

> *End angle (deg)*: The ending angle of the unrolling process. Quality threshold for penalizing bad shaped faces.  
> The value is in the range \[0..1\]  
> 0 accept any kind of face (no penalties),  
> 0.5 penalize faces with quality < 0.5, proportionally to their shape

`radius : float = 0`

> *Projection Radius*: If non zero, this parameter specifies the desired radius of the reference cylinder used for the projection. Changing this parameter affect the **X** horizontal scaling of the resulting mesh. If zero (default) the average distance of the mesh from the axis is chosen.

generate\_dust\_accumulation\_point\_cloud [](#generate_dust_accumulation_point_cloud "Link to this definition")

*MeshLab filter name*: ‘Dust Accumulation’

Simulate dust accumulation over the mesh generating a cloud of points lying on the current mesh

**Parameters:**

`dust_dir : numpy.ndarray[numpy.float64[3]] = [0, 1, 0]`

> *Direction*: Direction of the dust source

`nparticles : int = 3`

> *max particles x face*: Max Number of Dust Particles to Generate Per Face

`slippiness : float = 1`

> *s*: The surface slippines(large s means less sticky)

`adhesion : float = 0.2`

> *k*: Factor to model the general adhesion

`draw_texture : bool = False`

> *Draw Dust*: create a new texture saved in dirt\_texture.png

generate\_from\_selected\_faces [](#generate_from_selected_faces "Link to this definition")

*MeshLab filter name*: ‘Move selected faces to another layer’

Selected faces are moved (or duplicated) in a new layer. Warning! per-vertex and per-face user defined attributes will not be transferred.

**Parameters:**

`deleteoriginal : bool = True`

> *Delete original selection*: Deletes the original selected faces/vertices, thus splitting the mesh among layers.  
>   
> if false, the selected faces/vertices are duplicated in the new layer.

generate\_from\_selected\_vertices [](#generate_from_selected_vertices "Link to this definition")

*MeshLab filter name*: ‘Move selected vertices to another layer’

Selected vertices are moved (or duplicated) in a new layer. Warning! per-vertex user defined attributes will not be transferred.

**Parameters:**

`deleteoriginal : bool = True`

> *Delete original selection*: Deletes the original selected faces/vertices, thus splitting the mesh among layers.  
>   
> if false, the selected faces/vertices are duplicated in the new layer.

generate\_iso\_parametrization\_atlased\_mesh [](#generate_iso_parametrization_atlased_mesh "Link to this definition")

*MeshLab filter name*: ‘Iso Parametrization Build Atlased Mesh’

The filter build a new mesh with a standard atlased per wedge texture. The atlas is simply done by exploiting the low distortion, coarse, regular, mesh of the abstract domain  
For more details see:  
**N. Pietroni, M. Tarini and P. Cignoni**,  
['Almost isometric mesh parameterization through abstract domains'](http://vcg.isti.cnr.it/Publications/2010/PTC10/)  
IEEE Transaction of Visualization and Computer Graphics, 2010

**Parameters:**

`bordersize : float (bounded) = 0.1 [min: 0.01; max: 0.5]`

> *BorderSize ratio*: This parameter controls the amount of space that must be left between each diamond when building the atlas.It directly affects how many triangle are split during this conversion.  
> In abstract parametrization mesh triangles can naturally cross the triangles of the abstract domain, so when converting to a standard parametrization we must cut all the triangles that protrudes outside each diamond more than the specified threshold.The unit of the threshold is in percentage of the size of the diamond,The bigger the threshold the less triangles are split, but the more UV space is used (wasted).

generate\_iso\_parametrization\_remeshing [](#generate_iso_parametrization_remeshing "Link to this definition")

*MeshLab filter name*: ‘Iso Parametrization Remeshing’

Uniform Remeshing based on Isoparameterization, each triangle of the domain is recursively subdivided.  
For more details see:  
**N. Pietroni, M. Tarini and P. Cignoni**,  
['Almost isometric mesh parameterization through abstract domains'](http://vcg.isti.cnr.it/Publications/2010/PTC10/)  
IEEE Transaction of Visualization and Computer Graphics, 2010

**Parameters:**

`samplingrate : int = 10`

> *Sampling Rate*: This specify the sampling rate for remeshing. Must be greater than 2

generate\_marching\_cubes\_apss [](#generate_marching_cubes_apss "Link to this definition")

*MeshLab filter name*: ‘Marching Cubes (APSS)’

Extract the iso-surface (as a mesh) of a MLS surface defined by the current point set (or mesh)using the marching cubes algorithm. The coarse extraction is followed by an accurate projectionstep onto the MLS, and an extra zero removal procedure.  
  
This is the *algebraic point set surfaces* (APSS) variant which is based on the local fitting of algebraic spheres. It requires points equipped with oriented normals.  
For all the details about APSS see:  
Guennebaud and Gross, 'Algebraic Point Set Surfaces', Siggraph 2007, and  
Guennebaud et al., 'Dynamic Sampling and Rendering of APSS', Eurographics 2008

**Parameters:**

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sphericalparameter : float = 1`

> *MLS - Spherical parameter*: Control the curvature of the fitted spheres: 0 is equivalent to a pure plane fit,1 to a pure spherical fit, values between 0 and 1 gives intermediate results,while other real values might give interesting results, but take care with extremesettings!

`accuratenormal : bool = True`

> *Accurate normals*: If checked, use the accurate MLS gradient instead of the local approximationto compute the normals.

`resolution : int = 200`

> *Grid Resolution*: The resolution of the grid on which we run the marching cubes.This marching cube is memory friendly, so you can safely set large values up to 1000 or even more.

generate\_marching\_cubes\_rimls [](#generate_marching_cubes_rimls "Link to this definition")

*MeshLab filter name*: ‘Marching Cubes (RIMLS)’

Extract the iso-surface (as a mesh) of a MLS surface defined by the current point set (or mesh)using the marching cubes algorithm. The coarse extraction is followed by an accurate projectionstep onto the MLS, and an extra zero removal procedure.  
  
This is the Robust Implicit MLS (RIMLS) variant which is an extension of Implicit MLS preserving sharp features using non linear regression. For more details see:  
Oztireli, Guennebaud and Gross, 'Feature Preserving Point Set Surfaces based on Non-Linear Kernel Regression' Eurographics 2009.

**Parameters:**

`filterscale : float = 2`

> *MLS - Filter scale*: Scale of the spatial low pass filter.  
> It is relative to the radius (local point spacing) of the vertices.

`projectionaccuracy : float = 0.0001`

> *Projection - Accuracy (adv)*: Threshold value used to stop the projections.  
> This value is scaled by the mean point spacing to get the actual threshold.

`maxprojectioniters : int = 15`

> *Projection - Max iterations (adv)*: Max number of iterations for the projection.

`sigman : float = 0.75`

> *MLS - Sharpness*: Width of the filter used by the normal refitting weight.This weight function is a Gaussian on the distance between two unit vectors:the current gradient and the input normal. Therefore, typical value range between 0.5 (sharp) to 2 (smooth).

`maxrefittingiters : int = 3`

> *MLS - Max fitting iterations*: Max number of fitting iterations. (0 or 1 is equivalent to the standard IMLS)

`resolution : int = 200`

> *Grid Resolution*: The resolution of the grid on which we run the marching cubes.This marching cube is memory friendly, so you can safely set large values up to 1000 or even more.

generate\_plane\_fitting\_to\_selection [](#generate_plane_fitting_to_selection "Link to this definition")

*MeshLab filter name*: ‘Fit a plane to selection’

Create a quad on the plane fitting the selection

**Parameters:**

`extent : float = 1`

> *Extent (with respect to selection)*: How large is the plane, with respect to the size of the selection: 1.0 means as large as the selection, 1.1 means 10% larger then the selection

`subdiv : int = 3`

> *Plane XY subivisions*: Subdivision steps of plane borders

`hasuv : bool = False`

> *UV parametrized*: The created plane has an UV parametrization

`orientation : str = 'quasi-Straight Fit' (or int = 0)`

> Possible enum values:
> 
> > 0. `'quasi-Straight Fit'`
> > 1. `'Best Fit'`
> > 2. `'XZ Parallel'`
> > 3. `'YZ Parallel'`
> > 4. `'YX Parallel'`
> 
> *Plane orientation*: Orientation:**quasi-Straight Fit**: The fitting plane will be oriented (as much as possible) straight with the axeses.  
> **Best Fit**: The fitting plane will be oriented and sized trying to best fit to the selected area.  
> **\-- Parallel**: The fitting plane will be oriented with a side parallel with the chosen plane. WARNING: do not use if the selection is exactly parallel to a plane.

generate\_polyline\_from\_planar\_section [](#generate_polyline_from_planar_section "Link to this definition")

*MeshLab filter name*: ‘Compute Planar Section’

Compute the polyline representing a planar section (a slice) of a mesh; if the resulting polyline is closed the result is filled and also a triangular mesh representing the section is saved

**Parameters:**

`planeaxis : str = 'X Axis' (or int = 0)`

> Possible enum values:
> 
> > 0. `'X Axis'`
> > 1. `'Y Axis'`
> > 2. `'Z Axis'`
> > 3. `'Custom Axis'`
> 
> *Plane perpendicular to*: The Slicing plane will be done perpendicular to the axis

`customaxis : numpy.ndarray[numpy.float64[3]] = [0, 1, 0]`

> *Custom axis*: Specify a custom axis, this is only valid if the above parameter is set to Custom

`planeoffset : float = 0`

> *Cross plane offset*: Specify an offset of the cross-plane. The offset corresponds to the distance from the point specified in the plane reference parameter. By default (Cross plane offset == 0)

`relativeto : str = 'Origin' (or int = 2)`

> Possible enum values:
> 
> > 0. `'Bounding box center'`
> > 1. `'Bounding box min'`
> > 2. `'Origin'`
> 
> *plane reference*: Specify the reference from which the planes are shifted

`createsectionsurface : bool = False`

> *Create also section surface*: If selected, in addition to a layer with the section polyline, it will be created also a layer with a triangulated version of the section polyline. This only works if the section polyline is closed

`splitsurfacewithsection : bool = False`

> *Create also split surfaces*: If selected, it will create two layers with the portion of the mesh under and over the section plane. It requires manifoldness of the mesh.

generate\_polyline\_from\_selected\_edges [](#generate_polyline_from_selected_edges "Link to this definition")

*MeshLab filter name*: ‘Build a Polyline from Selected Edges’

Create a new Layer with an edge mesh composed only by the selected edges of the current mesh

generate\_polyline\_from\_selection\_perimeter [](#generate_polyline_from_selection_perimeter "Link to this definition")

*MeshLab filter name*: ‘Create Selection Perimeter Polyline’

Create a new Layer with an edge mesh (polyline) composed by the selected edges of the current mesh. It can be used to convert the boundary edges of a mesh into a polyline by selecting all the faces of the mesh.

generate\_resampled\_uniform\_mesh [](#generate_resampled_uniform_mesh "Link to this definition")

*MeshLab filter name*: ‘Uniform Mesh Resampling’

Create a new mesh that is a resampled version of the current one.  
The resampling is done by building a uniform volumetric representation where each voxel contains the signed distance from the original surface. The resampled surface is reconstructed using the **marching cube** algorithm over this volume.

**Parameters:**

`cellsize : PercentageValue = 2%`

> *Precision*: Size of the cell, the default is 1/50 of the box diag. Smaller cells give better precision at a higher computational cost. Remember that halving the cell size means that you build a volume 8 times larger.

`offset : PercentageValue = 50%`

> *Offset*: Offset of the created surface (i.e. distance of the created surface from the original one).  
> If offset is zero, the created surface passes on the original mesh itself. Values greater than zero mean an external surface, and lower than zero mean an internal surface.  
> In practice this value is the threshold passed to the Marching Cube algorithm to extract the isosurface from the distance field representation.

`mergeclosevert : bool = False`

> *Clean Vertices*: If true the mesh generated by MC will be cleaned by unifying vertices that are almost coincident

`discretize : bool = False`

> *Discretize*: If true the position of the intersected edge of the marching cube grid is not computed by linear interpolation, but it is placed in fixed middle position. As a consequence the resampled object will look severely aliased by a stairstep appearance.  
> Useful only for simulating the output of 3D printing devices.

`multisample : bool = False`

> *Multi-sample*: If true the distance field is more accurately compute by multisampling the volume (7 sample for each voxel). Much slower but less artifacts.

`absdist : bool = False`

> *Absolute Distance*: If true a **not** signed distance field is computed. In this case you have to choose a not zero Offset and a double surface is built around the original surface, inside and outside. Is useful to convert thin floating surfaces into *solid, thick meshes.*. t

generate\_sampling\_clustered\_vertex [](#generate_sampling_clustered_vertex "Link to this definition")

*MeshLab filter name*: ‘Clustered Vertex Sampling’

Create a new layer populated with a subsampling of the vertices of the current mesh; the subsampling is driven by a simple one-per-gridded cell strategy.

**Parameters:**

`threshold : PercentageValue = 1%`

> *Cell Size*: The size of the cell of the clustering grid. Smaller the cell finer the resulting mesh. For obtaining a very coarse mesh use larger values.

`sampling : str = 'Closest to center' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Average'`
> > 1. `'Closest to center'`
> 
> *Representative Strategy:*: **Average**: for each cell we take the average of the sample falling into. The resulting point is a new point.  
> **Closest to center**: for each cell we take the sample that is closest to the center of the cell. Chosen vertices are a subset of the original ones.

`selected : bool = False`

> *Only on Selection*: If true only for the filter is applied only on the selected subset of the mesh.

generate\_sampling\_element [](#generate_sampling_element "Link to this definition")

*MeshLab filter name*: ‘Mesh Element Sampling’

Create a new layer populated with a point sampling of the current mesh; at most one sample for each element of the mesh is created. Samples are taking in a uniform way, one for each element (vertex/edge/face); all the elements have the same probability of being chosen.

**Parameters:**

`sampling : str = 'Vertex' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Vertex'`
> > 1. `'Edge'`
> > 2. `'Face'`
> 
> *Element to sample:*: Choose what mesh element has to be used for the subsampling. At most one point sample will be added for each one of the chosen elements

`samplenum : int = 0`

> *Number of samples*: The desired number of elements that must be chosen. Being a subsampling of the original elements if this number should not be larger than the number of elements of the original mesh.

generate\_sampling\_montecarlo [](#generate_sampling_montecarlo "Link to this definition")

*MeshLab filter name*: ‘Montecarlo Sampling’

Create a new layer populated with a point sampling of the current mesh; samples are generated in a randomly uniform way, or with a distribution biased by the per-vertex quality values of the mesh.

**Parameters:**

`samplenum : int = 8`

> *Number of samples*: The desired number of samples. It can be smaller or larger than the mesh size, and according to the chosen sampling strategy it will try to adapt.

`weighted : bool = False`

> *Quality Weighted Sampling*: Use per vertex quality to drive the vertex sampling. The number of samples falling in each face is proportional to the face area multiplied by the average quality of the face vertices.

`perfacenormal : bool = False`

> *Per-Face Normal*: If true for each sample we take the normal of the sampled face, otherwise the normal interpolated from the vertex normals.

`radiusvariance : float = 1`

> *Radius Variance*: The radius of the disk is allowed to vary between r/var and r\*var. If this parameter is 1 the sampling is the same of the Poisson Disk Sampling

`exactnum : bool = True`

> *Exact Sample Number*: If the required total number of samples is not a strict exact requirement we can exploit a different algorithmbased on the choice of the number of samples inside each triangle by a random Poisson-distributed number with mean equal to the expected number of samples times the area of the triangle over the surface of the whole mesh.

`edgesampling : bool = False`

> *Sample CreaseEdge Only*: Restrict the sampling process to the crease edges only. Useful to sample in a more accurate way the feature edges of a mechanical mesh.

generate\_sampling\_poisson\_disk [](#generate_sampling_poisson_disk "Link to this definition")

*MeshLab filter name*: ‘Poisson-disk Sampling’

Create a new layer populated with a point sampling of the current mesh;samples are generated according to a Poisson-disk distribution, using the algorithm described in:  
**'Efficient and Flexible Sampling with Blue Noise Properties of Triangular Meshes'**  
Massimiliano Corsini, Paolo Cignoni, Roberto Scopigno  
IEEE TVCG 2012

**Parameters:**

`samplenum : int = 1000`

> *Number of samples*: The desired number of samples. The ray of the disk is calculated according to the sampling density.

`radius : PercentageValue = 0%`

> *Explicit Radius*: If not zero this parameter override the previous parameter to allow exact radius specification

`montecarlorate : int = 20`

> *MonterCarlo OverSampling*: The over-sampling rate that is used to generate the initial Montecarlo samples (e.g. if this parameter is *K* means that *K* x *poisson sample* points will be used). The generated Poisson-disk samples are a subset of these initial Montecarlo samples. Larger this number slows the process but make it a bit more accurate.

`savemontecarlo : bool = False`

> *Save Montecarlo*: If true, it will generate an additional Layer with the montecarlo sampling that was pruned to build the poisson distribution.

`approximategeodesicdistance : bool = False`

> *Approximate Geodesic Distance*: If true Poisson Disc distances are computed using an approximate geodesic distance, e.g. an euclidean distance weighted by a function of the difference between the normals of the two points.

`subsample : bool = False`

> *Base Mesh Subsampling*: If true the original vertices of the base mesh are used as base set of points. In this case the SampleNum should be obviously much smaller than the original vertex number.  
> Note that this option is very useful in the case you want to subsample a dense point cloud.

`refineflag : bool = False`

> *Refine Existing Samples*: If true the vertices of the below mesh are used as starting vertices, and they will utterly refined by adding more and more points until possible.

`refinemesh : int = 0`

> *Samples to be refined*: Used only if the above option is checked.

`bestsampleflag : bool = True`

> *Best Sample Heuristic*: If true it will use a simple heuristic for choosing the samples. At a small cost (it can slow a bit the process) it usually improve the maximality of the generated sampling.

`bestsamplepool : int = 10`

> *Best Sample Pool Size*: Used only if the Best Sample Flag is true. It control the number of attempt that it makes to get the best sample. It is reasonable that it is smaller than the Montecarlo oversampling factor.

`exactnumflag : bool = False`

> *Precise sample number*: If requested it will try to do a dicotomic search for the best poisson disk radius that will generate the requested number of samples with the below specified tolerance. Obviously it will takes much longer.

`exactnumtolerance : float = 0.005`

> *Precise sample number tolerance*: If a precise number of sample is requested, the sample number will be matched with the precision specified here. Precision is specified as a fraction of the sample number. so for example a precision of 0.005 over 1000 samples means that you can get 995 or 1005 samples.

`radiusvariance : float = 1`

> *Radius Variance*: The radius of the disk is allowed to vary between r and r\*var. If this parameter is 1 the sampling is the same of the Poisson Disk Sampling

generate\_sampling\_regular\_recursive [](#generate_sampling_regular_recursive "Link to this definition")

*MeshLab filter name*: ‘Regular Recursive Sampling’

The bounding box is recursively partitioned in a octree style, center of bbox are considered, when the center is nearer to the surface than a given threshold it is projected on it. It works also for building offsetted samples.

**Parameters:**

`cellsize : PercentageValue = 2%`

> *Precision*: Size of the cell, the default is 1/50 of the box diag. Smaller cells give better precision at a higher computational cost. Remember that halving the cell size means that you build a volume 8 times larger.

`offset : PercentageValue = 50%`

> *Offset*: Offset of the created surface (i.e. distance of the created surface from the original one).  
> If offset is zero, the created surface passes on the original mesh itself. Values greater than zero mean an external surface, and lower than zero mean an internal surface.  
> In practice this value is the threshold passed to the Marching Cube algorithm to extract the isosurface from the distance field representation.

generate\_sampling\_stratified\_triangle [](#generate_sampling_stratified_triangle "Link to this definition")

*MeshLab filter name*: ‘Stratified Triangle Sampling’

Create a new layer populated with a point sampling of the current mesh; to generate multiple samples inside a triangle each triangle is subdivided according to various *stratified* strategies. Distribution is often biased by triangle shape.

**Parameters:**

`samplenum : int = 100000`

> *Number of samples*: The desired number of samples. It can be smaller or larger than the mesh size, and according to the chosen sampling strategy it will try to adapt.

`sampling : str = 'Similar Triangle' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Similar Triangle'`
> > 1. `'Dual Similar Triangle'`
> > 2. `'Long Edge Subdiv'`
> > 3. `'Sample Edges'`
> > 4. `'Sample NonFaux Edges'`
> 
> *Element to sample:*: **Similar Triangle**: each triangle is subdivided into similar triangles and the internal vertices of these triangles are considered. This sampling leave space around edges and vertices for separate sampling of these entities.  
> **Dual Similar Triangle**: each triangle is subdivided into similar triangles and the internal vertices of these triangles are considered.  
> **Long Edge Subdiv** each triangle is recursively subdivided along the longest edge.  
> **Sample Edges** Only the edges of the mesh are uniformly sampled.  
> **Sample NonFaux Edges** Only the non-faux edges of the mesh are uniformly sampled.

`random : bool = False`

> *Random Sampling*: if true, for each (virtual) face we draw a random point, otherwise we pick the face midpoint.

generate\_sampling\_texel [](#generate_sampling_texel "Link to this definition")

*MeshLab filter name*: ‘Texel Sampling’

Create a new layer with a point sampling of the current mesh, a sample for each texel of the mesh is generated

**Parameters:**

`texturew : int = 512`

> *Texture Width*: A sample for each texel is generated, so the desired texture size is need, only samples for the texels falling inside some faces are generated.  
> Setting this param to 256 means that you get at most 256x256 = 65536 samples).  
> If this parameter is 0 the size of the current texture is chosen.

`textureh : int = 512`

> *Texture Height*: A sample for each texel is generated, so the desired texture size is need, only samples for the texels falling inside some faces are generated.  
> Setting this param to 256 means that you get at most 256x256 = 65536 samples)

`texturespace : bool = False`

> *UV Space Sampling*: The generated texel samples have their UV coords as point positions. The resulting point set is has a square domain, the texels/points, even if on a flat domain retain the original vertex normal to help a better perception of the original provenience.

`recovercolor : bool = False`

> *RecoverColor*: The generated point cloud has the current texture color

generate\_sampling\_volumetric [](#generate_sampling_volumetric "Link to this definition")

*MeshLab filter name*: ‘Volumetric Sampling’

Compute a volumetric sampling over a watertight mesh.

**Parameters:**

`samplesurfradius : PercentageValue = 0.2%`

> *Surface Sampling Radius*: Surface Sampling is used only as an optimization.

`samplevolnum : int = 200000`

> *Volume Sample Num.*: Number of volumetric samples scattered inside the mesh and used for choosing the voronoi seeds and performing the Lloyd relaxation for having a centroidal voronoi diagram.

`poissonfiltering : bool = True`

> *Poisson Filtering*: If true the base montecarlo sampling of the volume is filtered to get a poisson disk volumetric distribution.

`poissonradius : PercentageValue = 1%`

> *Poisson Radius*: Number of voxel per side in the volumetric representation.

generate\_sampling\_voronoi [](#generate_sampling_voronoi "Link to this definition")

*MeshLab filter name*: ‘Voronoi Sampling’

Compute a point sampling over a mesh and perform a Lloyd relaxation. The filter selects the vertices of the starting mesh that corresponds to the sampled points.  
Two additional layers containing a voronoi tassellation are created, one as a mesh and one as a polyline. To save the sampled vertices in a different layer just use the 'move selected vertices to a new layer' filter

**Parameters:**

`iternum : int = 10`

> *Iteration*: number of iterations

`samplenum : int = 10`

> *Sample Num.*: Number of samples

`radiusvariance : float = 1`

> *Radius Variance*: The distance metric will vary along the surface between 1/x and x, linearly according to the scalar field specified by the quality.

`colorstrategy : str = 'Seed Distance' (or int = 1)`

> Possible enum values:
> 
> > 0. `'None'`
> > 1. `'Seed Distance'`
> > 2. `'Border Distance'`
> > 3. `'Region Area'`
> 
> *Color Strategy*:

`distancetype : str = 'Euclidean' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Euclidean'`
> > 1. `'Quality Weighted'`
> > 2. `'Anisotropic'`
> 
> *Distance Type*:

`preprocessflag : bool = False`

> *Preprocessing*:

`refinefactor : int = 10`

> *Refinement Factor*: To ensure good convergence the mesh should be more complex than the voronoi partitioning. This number affect how much the mesh is refined according to the required number of samples.

`perturbprobability : float = 0`

> *Perturbation Probability*: To ensure good convergence the mesh should be more complex than the voronoi partitioning. This number affect how much the mesh is refined according to the required number of samples.

`perturbamount : float = 0.001`

> *Perturbation Amount*: To ensure good convergence the mesh should be more complex than the voronoi partitioning. This number affect how much the mesh is refined according to the required number of samples.

`randomseed : int = 0`

> *Random seed*: To ensure repeatability you can specify the random seed used. If 0 the random seed is tied to the current clock.

`relaxtype : str = 'Squared Distance' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Geodesic'`
> > 1. `'Squared Distance'`
> > 2. `'Restricted'`
> 
> *Relax Type*: At each relaxation step we search for each voronoi region the new position of the seed. According to the classical LLoyd relaxation strategy it should have been placed onto the barycenter of the region. Over a surface we have two different strategies:
> - Geodesic: the seed is placed onto the vertex that maximize the geodesic distance from the border of the region
> - Squared Distance: the seed is placed in the vertex that minimize the squared sum of the distances from all the pints of the region.
> - Restricted: the seed is placed in the barycenter of current voronoi region. Even if it is outside the surface. During the relaxation process the seed is free to move off the surface in a continuous way. Re-association to vertex is done at the end..

generate\_simplified\_point\_cloud [](#generate_simplified_point_cloud "Link to this definition")

*MeshLab filter name*: ‘Point Cloud Simplification’

Create a new layer populated with a simplified version of the current point cloud. The simplification is performed by subsampling the original point cloud using a Poisson Disk strategy.

**Parameters:**

`samplenum : int = 1000`

> *Number of samples*: The desired number of samples. The ray of the disk is calculated according to the sampling density.

`radius : PercentageValue = 0%`

> *Explicit Radius*: If not zero this parameter override the previous parameter to allow exact radius specification

`bestsampleflag : bool = True`

> *Best Sample Heuristic*: If true it will use a simple heuristic for choosing the samples. At a small cost (it can slow a bit the process) it usually improve the maximality of the generated sampling.

`bestsamplepool : int = 10`

> *Best Sample Pool Size*: Used only if the Best Sample Flag is true. It control the number of attempt that it makes to get the best sample. It is reasonable that it is smaller than the Montecarlo oversampling factor.

`exactnumflag : bool = False`

> *Precise sample number*: If requested it will try to do a dicotomic search for the best poisson disk radius that will generate the requested number of samples with the below specified tolerance. Obviously it will takes much longer.

`exactnumtolerance : float = 0.005`

> *Precise sample number tolerance*: If a precise number of sample is requested, the sample number will be matched with the precision specified here. Precision is specified as a fraction of the sample number. so for example a precision of 0.005 over 1000 samples means that you can get 995 or 1005 samples.

generate\_solid\_wireframe [](#generate_solid_wireframe "Link to this definition")

*MeshLab filter name*: ‘Create Solid Wireframe’

**Parameters:**

`edgecylflag : bool = True`

> *Edge -> Cyl.*: If True all the edges are converted into cylinders.

`edgecylradius : PercentageValue = 1%`

> *Edge Cylinder Rad.*: The radius of the cylinder replacing each edge.

`vertcylflag : bool = False`

> *Vertex -> Cyl.*: If True all the vertices are converted into cylinders.

`vertcylradius : PercentageValue = 1%`

> *Vertex Cylinder Rad.*: The radius of the cylinder replacing each vertex.

`vertsphflag : bool = True`

> *Vertex -> Sph.*: If True all the vertices are converted into sphere.

`vertsphradius : PercentageValue = 1%`

> *Vertex Sphere Rad.*: The radius of the sphere replacing each vertex.

`faceextflag : bool = True`

> *Face -> Prism*: If True all the faces are converted into prism.

`faceextheight : PercentageValue = 0.5%`

> *Face Prism Height*: The Height of the prism that is substituted with each face.

`faceextinset : PercentageValue = 0.5%`

> *Face Prism Inset*: The inset radius of each prism, e.g. how much it is moved toward the inside each vertex on the border of the prism.

`edgefauxflag : bool = True`

> *Ignore faux edges*: If true only the Non-Faux edges will be considered for conversion.

`cylindersidenum : int = 16`

> *Cylinder Side*: Number of sides of the cylinder (both edge and vertex).

generate\_splitting\_by\_connected\_components [](#generate_splitting_by_connected_components "Link to this definition")

*MeshLab filter name*: ‘Split in Connected Components’

Split current Layer into many layers, one for each connected components

**Parameters:**

`delete_source_mesh : bool = False`

> *Delete source mesh*: Deletes the source mesh after all the connected component meshes are generated.

generate\_surface\_reconstruction\_ball\_pivoting [](#generate_surface_reconstruction_ball_pivoting "Link to this definition")

*MeshLab filter name*: ‘Surface Reconstruction: Ball Pivoting’

Given a point cloud with normals it reconstructs a surface using the **Ball Pivoting Algorithm**.Starting with a seed triangle, the BPA algorithm pivots a ball of the given radius around the already formed edges until it touches another point, forming another triangle. The process continues until all reachable edges have been tried. This surface reconstruction algorithm uses the existing points without creating new ones. Works better with uniformly sampled point clouds. If needed first perform a poisson disk subsampling of the point cloud.  
Bernardini F., Mittleman J., Rushmeier H., Silva C., Taubin G.  
**The ball-pivoting algorithm for surface reconstruction.**  
IEEE TVCG 1999

**Parameters:**

`ballradius : PercentageValue = 0%`

> *Pivoting Ball radius (0 autoguess)*: The radius of the ball pivoting (rolling) over the set of points. Gaps that are larger than the ball radius will not be filled; similarly the small pits that are smaller than the ball radius will be filled.

`clustering : float = 20`

> *Clustering radius (% of ball radius)*: To avoid the creation of too small triangles, if a vertex is found too close to a previous one, it is clustered/merged with it.

`creasethr : float = 90`

> *Angle Threshold (degrees)*: If we encounter a crease angle that is too large we should stop the ball rolling

`deletefaces : bool = False`

> *Delete initial set of faces*: if true all the initial faces of the mesh are deleted and the whole surface is rebuilt from scratch. Otherwise the current faces are used as a starting point. Useful if you run the algorithm multiple times with an increasing ball radius.

generate\_surface\_reconstruction\_screened\_poisson [](#generate_surface_reconstruction_screened_poisson "Link to this definition")

*MeshLab filter name*: ‘Surface Reconstruction: Screened Poisson’

This surface reconstruction algorithm creates watertight surfaces from oriented point sets.  
The filter uses the original code of Michael Kazhdan and Matthew Bolitho implementing the algorithm described in the following paper:  
*Michael Kazhdan, Hugues Hoppe*,  
**"Screened Poisson surface reconstruction"**  

**Parameters:**

`visiblelayer : bool = False`

> *Merge all visible layers*: Enabling this flag means that all the visible layers will be used for providing the points.

`depth : int = 8`

> *Reconstruction Depth*: This integer is the maximum depth of the tree that will be used for surface reconstruction. Running at depth d corresponds to solving on a voxel grid whose resolution is no larger than 2^d x 2^d x 2^d. Note that since the reconstructor adapts the octree to the sampling density, the specified reconstruction depth is only an upper bound. The default value for this parameter is 8.

`fulldepth : int = 5`

> *Adaptive Octree Depth*: This integer specifies the depth beyond depth the octree will be adapted. At coarser depths, the octree will be complete, containing all 2^d x 2^d x 2^d nodes. The default value for this parameter is 5.

`cgdepth : int = 0`

> *Conjugate Gradients Depth*: This integer is the depth up to which a conjugate-gradients solver will be used to solve the linear system. Beyond this depth Gauss-Seidel relaxation will be used. The default value for this parameter is 0.

`scale : float = 1.1`

> *Scale Factor*: This floating point value specifies the ratio between the diameter of the cube used for reconstruction and the diameter of the samples' bounding cube. The default value is 1.1.

`samplespernode : float = 1.5`

> *Minimum Number of Samples*: This floating point value specifies the minimum number of sample points that should fall within an octree node as the octree construction is adapted to sampling density. For noise-free samples, small values in the range \[1.0 - 5.0\] can be used. For more noisy samples, larger values in the range \[15.0 - 20.0\] may be needed to provide a smoother, noise-reduced, reconstruction. The default value is 1.5.

`pointweight : float = 4`

> *Interpolation Weight*: This floating point value specifies the importants that interpolation of the point samples is given in the formulation of the screened Poisson equation. The results of the original (unscreened) Poisson Reconstruction can be obtained by setting this value to 0. The default value for this parameter is 4.

`iters : int = 8`

> *Gauss-Seidel Relaxations*: This integer value specifies the number of Gauss-Seidel relaxations to be performed at each level of the hierarchy. The default value for this parameter is 8.

`confidence : bool = False`

> *Confidence Flag*: Enabling this flag tells the reconstructor to use the quality as confidence information; this is done by scaling the unit normals with the quality values. When the flag is not enabled, all normals are normalized to have unit-length prior to reconstruction.

`preclean : bool = False`

> *Pre-Clean*: Enabling this flag force a cleaning pre-pass on the data removing all unreferenced vertices or vertices with null normals.

`threads : int = 16`

> *Number Threads*: Maximum number of threads that the reconstruction algorithm can use.

generate\_surface\_reconstruction\_vcg [](#generate_surface_reconstruction_vcg "Link to this definition")

*MeshLab filter name*: ‘Surface Reconstruction: VCG’

The surface reconstrction algorithm that have been used for a long time inside the ISTI-Visual Computer Lab.It is mostly a variant of the Curless et al. e.g. a volumetric approach with some original weighting schemes,a different expansion rule, and another approach to hole filling through volume dilation/relaxations.  
The filter is applied to **ALL** the visible layers. In practice, all the meshes/point clouds that are currently *visible* are used to build the volumetric distance field.

**Parameters:**

`voxsize : PercentageValue = 1%`

> *Voxel Side*: VoxelSide

`subdiv : int = 1`

> *SubVol Splitting*: The level of recursive splitting of the subvolume reconstruction process. A value of '3' means that a 3x3x3 regular space subdivision is created and the reconstruction process generate 8 matching meshes. It is useful for reconsruction objects at a very high resolution. Default value (1) means no splitting.

`geodesic : float = 2`

> *Geodesic Weighting*: The influence of each range map is weighted with its geodesic distance from the borders. In this way when two (or more ) range maps overlaps their contribution blends smoothly hiding possible misalignments.

`openresult : bool = True`

> *Show Result*: if not checked the result is only saved into the current directory

`smoothnum : int = 1`

> *Volume Laplacian iter*: How many volume smoothing step are performed to clean out the eventually noisy borders

`widenum : int = 3`

> *Widening*: How many voxel the field is expanded. Larger this value more holes will be filled

`mergecolor : bool = False`

> *Vertex Splatting*: This option use a different way to build up the volume, instead of using rasterization of the triangular face it splat the vertices into the grids. It works under the assumption that you have at least one sample for each voxel of your reconstructed volume.

`simplification : bool = False`

> *Post Merge simplification*: After the merging an automatic simplification step is performed.

`normalsmooth : int = 3`

> *PreSmooth iter*: How many times, before converting meshes into volume, the normal of the surface are smoothed. It is useful only to get more smooth expansion in case of noisy borders.

generate\_voronoi\_atlas\_parametrization [](#generate_voronoi_atlas_parametrization "Link to this definition")

*MeshLab filter name*: ‘Parametrization: Voronoi Atlas’

Build an atlased parametrization based on a geodesic voronoi partitioning of the surface and parametrizing each region using Harmonic Mapping. For the parametrization of the disk like voronoi regions the used method is:  
**Ulrich Pinkall, Konrad Polthier**  
*Computing Discrete Minimal Surfaces and Their Conjugates*  
Experimental Mathematics, Vol 2 (1), 1993.

**Parameters:**

`regionnum : int = 10`

> *Approx. Region Num*: An estimation of the number of regions that must be generated. Smaller regions could lead to parametrizations with smaller distortion.

`overlapflag : bool = False`

> *Overlap*: If checked the resulting parametrization will be composed by *overlapping* regions, e.g. the resulting mesh will have duplicated faces: each region will have a ring of ovelapping duplicate faces that will ensure that border regions will be parametrized in the atlas twice. This is quite useful for building mipmap robust atlases

generate\_voronoi\_filtering [](#generate_voronoi_filtering "Link to this definition")

*MeshLab filter name*: ‘Voronoi Filtering’

Compute a **Voronoi filtering** (Amenta and Bern 1998) with Qhull library (http://www.qhull.org/).  
  
The algorithm calculates a triangulation of the input point cloud without requiring vertex normals.It uses a subset of the Voronoi vertices to remove triangles from the Delaunay triangulation.  
After computing the Voronoi diagram, foreach sample point it chooses the two farthest opposite Voronoi vertices.Then computes a Delaunay triangulation of the sample points and the selected Voronoi vertices, and keep only those triangles in witch all three vertices are sample points.

**Parameters:**

`threshold : float (bounded) = 10 [min: 0; max: 2000]`

> *Pole Discard Thr*: Threshold used to discard the Voronoi vertices too far from the origin.We discard vertices are further than this factor times the bbox diagonal  
> Growing values of this value will add more Voronoi vertices for a better tightier surface reconstruction.On the other hand they will increase processing time and could cause numerical problems to the qhull library.

generate\_voronoi\_scaffolding [](#generate_voronoi_scaffolding "Link to this definition")

*MeshLab filter name*: ‘Voronoi Scaffolding’

Compute a volumetric sampling over a watertight mesh.

**Parameters:**

`samplesurfradius : PercentageValue = 1%`

> *Surface Sampling Radius*: Surface Sampling is used only as an optimization.

`samplevolnum : int = 100000`

> *Volume Sample Num.*: Number of volumetric samples scattered inside the mesh and used for choosing the voronoi seeds and performing the Lloyd relaxation for having a centroidal voronoi diagram.

`voxelres : int = 50`

> *Volume Side Resolution*: Number of voxel per side in the volumetric representation.

`isothr : float = 1`

> *Width of the entity (in voxel)*: Number of voxel per side in the volumetric representation.

`smoothstep : int = 3`

> *Smooth Step*: Number of voxel per side in the volumetric representation.

`relaxstep : int = 5`

> *Lloyd Relax Step*: Number of Lloyd relaxation step to get a better distribution of the voronoi seeds.

`surfflag : bool = True`

> *Add original surface*: Number of voxel per side in the volumetric representation.

`elemtype : str = 'Edge' (or int = 1)`

> Possible enum values:
> 
> > 0. `'Seed'`
> > 1. `'Edge'`
> > 2. `'Face'`
> 
> *Voronoi Element*:

get\_area\_and\_perimeter\_of\_selection [](#get_area_and_perimeter_of_selection "Link to this definition")

*MeshLab filter name*: ‘Compute Area/Perimeter of selection’

Compute area and perimeter of the FACE selection. Open the layer dialog to see the results.

get\_depth\_complexity [](#get_depth_complexity "Link to this definition")

*MeshLab filter name*: ‘Depth complexity’

Calculate the depth complexity of the mesh, that is: the maximum number of layers that a ray can hit while traversing the mesh. To have a correct value, you should specify and high value in the peeling iteration parameter. You can read the result in the MeshLab log window. **If warnings are not present, you have the exact value, otherwise try increasing the peeling iteration parameter. After having calculated the correct value,you can ignore further warnings that you may get using that value.**.

**Parameters:**

`onprimitive : str = 'On vertices' (or int = 0)`

> Possible enum values:
> 
> > 0. `'On vertices'`
> > 1. `'On Faces'`
> 
> *Metric:*: Choose whether to trace rays from faces or from vertices.

`numberrays : int = 128`

> *Number of rays:* : The number of rays that will be casted around the normals.

`depthtexturesize : int = 512`

> *Depth texture size*: Size of the depth texture for depth peeling. Higher resolutions provide better sampling of the mesh, with a small performance penalty.

`peelingiteration : int = 10`

> *Peeling Iteration*: Number of depth peeling iteration. Actually is the maximum number of layers that a ray can hit while traversing the mesh. For example, in the case of a sphere, you should specify 2 in this parameter. For a torus, specify 4. **For more complex geometry you should run the depth complexity filter to know the exact value**.

`peelingtolerance : float = 1e-07`

> *Peeling Tolerance*: Depth tolerance used during depth peeling. This is the threshold used to differentiate layers between each others.Two elements whose distance is below this value will be considered as belonging to the same layer.

get\_geometric\_measures [](#get_geometric_measures "Link to this definition")

*MeshLab filter name*: ‘Compute Geometric Measures’

Compute a set of geometric measures of a mesh/pointcloud. Bounding box extents and diagonal, principal axis, thin shell barycenter (mesh only), vertex barycenter and quality-weighted barycenter (pointcloud only), surface area (mesh only), volume (closed mesh) and Inertia tensor Matrix (closed mesh). Open the layer dialog to see the results.

get\_hausdorff\_distance [](#get_hausdorff_distance "Link to this definition")

*MeshLab filter name*: ‘Hausdorff Distance’

Compute the Hausdorff Distance between two layers, sampling one of the two and finding for each sample the closest point over the other mesh. Distance is stored in vertex quality of the sampled mesh.

**Parameters:**

`sampledmesh : int = 0`

> *Sampled Mesh*: The mesh whose surface is sampled. For each sample we search the closest point on the Target Mesh.

`targetmesh : int = 0`

> *Target Mesh*: The mesh that is sampled for the comparison.

`savesample : bool = False`

> *Save Samples*: Save the position and distance of all the used samples on both the two surfaces, creating two new layers with two point clouds representing the used samples.

`samplevert : bool = True`

> *Sample Vertices*: For the search of maxima it is useful to sample vertices and edges of the mesh with a greater care. It is quite probably the the farthest points falls along edges or on mesh vertices, and with uniform montecarlo sampling approachesthe probability of taking a sample over a vertex or an edge is theoretically null.  
> On the other hand this kind of sampling could make the overall sampling distribution slightly biased and slightly affects the cumulative results.

`sampleedge : bool = False`

> *Sample Edges*: See the above comment.

`samplefauxedge : bool = False`

> *Sample FauxEdge*: See the above comment.

`sampleface : bool = False`

> *Sample Faces*: See the above comment.

`samplenum : int = 8`

> *Number of samples*: The desired number of samples. It can be smaller or larger than the mesh size, and according to the chosen sampling strategy it will try to adapt.

`maxdist : PercentageValue = 50%`

> *Max Distance*: Sample points for which we do not find anything within this distance are rejected and not considered neither for averaging nor for max.

get\_overlapping\_meshes\_graph [](#get_overlapping_meshes_graph "Link to this definition")

*MeshLab filter name*: ‘Overlapping Meshes’

Use an occupancy grid to see which meshes overlap between themselves.

**Parameters:**

`ogsize : int = 50000`

> *Occupancy Grid Size*: To compute the overlap between range maps we discretize them into voxel and count them (both for area and overlap); This parameter affect the resolution of the voxelization process. Using a too fine voxelization can...

get\_scalar\_histogram\_per\_face [](#get_scalar_histogram_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Quality Histogram’

Compute an histogram of the values of the per-face quality.

**Parameters:**

`histmin : float = 0`

> *Hist Min*: The faces are displaced of a vector whose norm is bounded by this value

`histmax : float = 0`

> *Hist Max*: The faces are displaced of a vector whose norm is bounded by this value

`areaweighted : bool = False`

> *Area Weighted*: If false, the histogram will report the number of faces with quality values falling in each bin of the histogram. If true each bin of the histogram will report the approximate area of the mesh with that range of values.

`binnum : int = 20`

> *Bin number*: The number of bins of the histogram. E.g. the number of intervals in which the min..max range is subdivided into.

get\_scalar\_histogram\_per\_vertex [](#get_scalar_histogram_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Quality Histogram’

Compute an histogram of the values of the per-vertex quality. It can be useful to evaluate the distribution of the quality value over the surface. It can be discrete (e.g. based on vertex count or area weighted).

**Parameters:**

`histmin : float = 0`

> *Hist Min*: The vertex are displaced of a vector whose norm is bounded by this value

`histmax : float = 0`

> *Hist Max*: The vertex are displaced of a vector whose norm is bounded by this value

`areaweighted : bool = False`

> *Area Weighted*: If false, the histogram will report the number of vertices with quality values falling in each bin of the histogram. If true each bin of the histogram will report the approximate area of the mesh with that range of values. Area is computed by assigning to each vertex one third of the area all the incident triangles.

`binnum : int = 20`

> *Bin number*: The number of bins of the histogram. E.g. the number of intervals in which the min..max range is subdivided into.

get\_scalar\_statistics\_per\_face [](#get_scalar_statistics_per_face "Link to this definition")

*MeshLab filter name*: ‘Per Face Quality Stat’

Compute some aggregate statistics over the per vertex quality, like Min, Max, Average, StdDev and Variance.

get\_scalar\_statistics\_per\_vertex [](#get_scalar_statistics_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Per Vertex Quality Stat’

Compute some aggregate statistics over the per vertex quality, like Min, Max, Average, StdDev and Variance.

get\_topological\_measures [](#get_topological_measures "Link to this definition")

*MeshLab filter name*: ‘Compute Topological Measures’

Compute a set of topological measures over a mesh.

get\_topological\_measures\_from\_quad\_mesh [](#get_topological_measures_from_quad_mesh "Link to this definition")

*MeshLab filter name*: ‘Compute Topological Measures for Quad Meshes’

Compute a set of topological measures over a quad mesh.

load\_active\_raster\_cameras [](#load_active_raster_cameras "Link to this definition")

*MeshLab filter name*: ‘Import cameras for active rasters from file’

Import cameras for active rasters from.out or Agisoft.xml formats

**Parameters:**

`importfile : str = ''`

> *Choose the camera file to be imported*: It's possible to import both Bundler.out and Agisoft.xml files. In both cases, distortion parameters won't be imported. In the case of Agisoft, it's necessary to undistort the images before exporting the xml file.

meshing\_close\_holes [](#meshing_close_holes "Link to this definition")

*MeshLab filter name*: ‘Close Holes’

Close holes whose boundary is composed by a number of edges smaller than a given trheshold

**Parameters:**

`maxholesize : int = 30`

> *Max size to be closed* : The size is expressed as number of edges composing the hole boundary

`selected : bool = False`

> *Close holes with selected faces*: Only the holes with at least one of the boundary faces selected are closed

`newfaceselected : bool = True`

> *Select the newly created faces*: After closing a hole the faces that have been created are left selected. Any previous selection is lost. Useful for example for smoothing the newly created holes.

`selfintersection : bool = True`

> *Prevent creation of selfIntersecting faces*: When closing an holes it tries to prevent the creation of faces that intersect faces adjacent to the boundary of the hole. It is an heuristic, non intersetcting hole filling can be NP-complete.

`refinehole : bool = False`

> *Refine Filled Hole*: After closing the hole it will refine the newly created triangles to make the surface more smooth and the triangulation more evenly spaced

`refineholeedgelen : PercentageValue = 3%`

> *Hole Refinement Edge Len*: The target edge lenght of the triangulation inside the filled hole.

meshing\_cut\_along\_crease\_edges [](#meshing_cut_along_crease_edges "Link to this definition")

*MeshLab filter name*: ‘Cut mesh along crease edges’

Cut the mesh along crease edges, duplicating the vertices as necessary. Crease (or sharp) edges are defined according to the variation of normal of the adjacent faces.

**Parameters:**

`angledeg : float = 90`

> *Crease Angle (degree)*: If the angle between the normals of two adjacent faces is **larger** that this threshold the edge is considered a creased and the mesh is cut along it.

meshing\_decimation\_clustering [](#meshing_decimation_clustering "Link to this definition")

*MeshLab filter name*: ‘Simplification: Clustering Decimation’

Collapse vertices by creating a three dimensional grid enveloping the mesh and discretizes them based on the cells of this grid

**Parameters:**

`threshold : PercentageValue = 1%`

> *Cell Size*: The size of the cell of the clustering grid. Smaller the cell finer the resulting mesh. For obtaining a very coarse mesh use larger values.

meshing\_decimation\_edge\_collapse\_for\_marching\_cube\_meshes [](#meshing_decimation_edge_collapse_for_marching_cube_meshes "Link to this definition")

*MeshLab filter name*: ‘Simplification: Edge Collapse for Marching Cube meshes’

A simplification/cleaning algorithm that works ONLY on meshes generated by Marching Cubes algorithm.

meshing\_decimation\_quadric\_edge\_collapse [](#meshing_decimation_quadric_edge_collapse "Link to this definition")

*MeshLab filter name*: ‘Simplification: Quadric Edge Collapse Decimation’

Simplify a mesh using a quadric based edge-collapse strategy. A variant of the well known Garland and Heckbert simplification algorithm with different weighting schemes to better cope with aspect ration and planar/degenerate quadrics areas.  
See:  
*M. Garland and P. Heckbert.*  
**Surface Simplification Using Quadric Error Metrics** ([pdf](http://mgarland.org/papers/quadrics.pdf))  
In Proceedings of SIGGRAPH 97.  
  

**Parameters:**

`targetfacenum : int = 6`

> *Target number of faces*: The desired final number of faces.

`targetperc : float = 0`

> *Percentage reduction (0..1)*: If non zero, this parameter specifies the desired final size of the mesh as a percentage of the initial size.

`qualitythr : float = 0.3`

> *Quality threshold*: Quality threshold for penalizing bad shaped faces.  
> The value is in the range \[0..1\]  
> 0 accept any kind of face (no penalties),  
> 0.5 penalize faces with quality < 0.5, proportionally to their shape

`preserveboundary : bool = False`

> *Preserve Boundary of the mesh*: The simplification process tries to do not affect mesh boundaries during simplification

`boundaryweight : float = 1`

> *Boundary Preserving Weight*: The importance of the boundary during simplification. Default (1.0) means that the boundary has the same importance of the rest. Values greater than 1.0 raise boundary importance and has the effect of removing less vertices on the border. Admitted range of values (0,+inf).

`preservenormal : bool = False`

> *Preserve Normal*: Try to avoid face flipping effects and try to preserve the original orientation of the surface

`preservetopology : bool = False`

> *Preserve Topology*: Avoid all the collapses that should cause a topology change in the mesh (like closing holes, squeezing handles, etc). If checked the genus of the mesh should stay unchanged.

`optimalplacement : bool = True`

> *Optimal position of simplified vertices*: Each collapsed vertex is placed in the position minimizing the quadric error.  
> It can fail (creating bad spikes) in case of very flat areas.  
> If disabled edges are collapsed onto one of the two original vertices and the final mesh is composed by a subset of the original vertices.

`planarquadric : bool = False`

> *Planar Simplification*: Add additional simplification constraints that improves the quality of the simplification of the planar portion of the mesh, as a side effect, more triangles will be preserved in flat areas (allowing better shaped triangles).

`planarweight : float = 0.001`

> *Planar Simp. Weight*: How much we should try to preserve the triangles in the planar regions. If you lower this value planar areas will be simplified more.

`qualityweight : bool = False`

> *Weighted Simplification*: Use the Per-Vertex quality as a weighting factor for the simplification. The weight is used as a error amplification value, so a vertex with a high quality value will not be simplified and a portion of the mesh with low quality values will be aggressively simplified.

`autoclean : bool = True`

> *Post-simplification cleaning*: After the simplification an additional set of steps is performed to clean the mesh (unreferenced vertices, bad faces, etc)

`selected : bool = False`

> *Simplify only selected faces*: The simplification is applied only to the selected set of faces.  
> Take care of the target number of faces!

meshing\_decimation\_quadric\_edge\_collapse\_with\_texture [](#meshing_decimation_quadric_edge_collapse_with_texture "Link to this definition")

*MeshLab filter name*: ‘Simplification: Quadric Edge Collapse Decimation (with texture)’

Simplify a textured mesh using a Quadric based Edge Collapse Strategy preserving UV parametrization. Inspired in the QSLIM surface simplification algorithm by Michael Garland, which turned into the industry standard method for mesh simplification.  
See:  
*M. Garland and P. Heckbert.*  
**Simplifying Surfaces with Color and Texture using Quadric Error Metrics** ([pdf](http://mgarland.org/papers/quadric2.pdf))  
In Proceedings of IEEE Visualization 98.  
  

**Parameters:**

`targetfacenum : int = 6`

> *Target number of faces*:

`targetperc : float = 0`

> *Percentage reduction (0..1)*: If non zero, this parameter specifies the desired final size of the mesh as a percentage of the initial mesh.

`qualitythr : float = 0.3`

> *Quality threshold*: Quality threshold for penalizing bad shaped faces.  
> The value is in the range \[0..1\]  
> 0 accept any kind of face (no penalties),  
> 0.5 penalize faces with quality < 0.5, proportionally to their shape

`extratcoordw : float = 1`

> *Texture Weight*: Additional weight for each extra Texture Coordinates for every (selected) vertex

`preserveboundary : bool = False`

> *Preserve Boundary of the mesh*: The simplification process tries not to destroy mesh boundaries

`boundaryweight : float = 1`

> *Boundary Preserving Weight*: The importance of the boundary during simplification. Default (1.0) means that the boundary has the same importance of the rest. Values greater than 1.0 raise boundary importance and has the effect of removing less vertices on the border. Admitted range of values (0,+inf).

`optimalplacement : bool = True`

> *Optimal position of simplified vertices*: Each collapsed vertex is placed in the position minimizing the quadric error.  
> It can fail (creating bad spikes) in case of very flat areas.  
> If disabled edges are collapsed onto one of the two original vertices and the final mesh is composed by a subset of the original vertices.

`preservenormal : bool = False`

> *Preserve Normal*: Try to avoid face flipping effects and try to preserve the original orientation of the surface

`planarquadric : bool = False`

> *Planar Simplification*: Add additional simplification constraints that improves the quality of the simplification of the planar portion of the mesh.

`selected : bool = False`

> *Simplify only selected faces*: The simplification is applied only to the selected set of faces.  
> Take care of the target number of faces!

meshing\_edge\_flip\_by\_curvature\_optimization [](#meshing_edge_flip_by_curvature_optimization "Link to this definition")

*MeshLab filter name*: ‘Curvature flipping optimization’

Mesh optimization by edge flipping, to improve local mesh curvature

**Parameters:**

`selection : bool = False`

> *Update selection*: Apply edge flip optimization on selected faces only

`pthreshold : float = 1`

> *Angle Thr (deg)*: To avoid excessive flipping/swapping we consider only couple of faces with a significant diedral angle (e.g. greater than the indicated threshold).

`curvtype : str = 'mean' (or int = 0)`

> Possible enum values:
> 
> > 0. `'mean'`
> > 1. `'norm squared'`
> > 2. `'absolute'`
> 
> *Curvature metric*:
> 
> Choose a metric to compute surface curvature on vertices  
> H = mean curv, K = gaussian curv, A = area per vertex  
>   
> 1: Mean curvature = H  
> 2: Norm squared mean curvature = (H \* H) / A  
> 3: Absolute curvature:  
> if(K >= 0) return 2 \* H  
> else return 2 \* sqrt(H ^ 2 - A \* K)

meshing\_edge\_flip\_by\_planar\_optimization [](#meshing_edge_flip_by_planar_optimization "Link to this definition")

*MeshLab filter name*: ‘Planar flipping optimization’

Mesh optimization by edge flipping, to improve local triangle quality

**Parameters:**

`selection : bool = False`

> *Update selection*: Apply edge flip optimization on selected faces only

`pthreshold : float = 1`

> *Planar threshold (deg)*: angle threshold for planar faces (degrees)

`planartype : str = 'area/max side' (or int = 0)`

> Possible enum values:
> 
> > 0. `'area/max side'`
> > 1. `'inradius/circumradius'`
> > 2. `'mean ratio'`
> > 3. `'delaunay'`
> > 4. `'topology'`
> 
> *Planar metric*:
> 
> Choose a metric to define the planar flip operation  
>   
> Triangle quality based  
> 1: minimum ratio height/edge among the edges  
> 2: ratio between radii of incenter and circumcenter  
> 3: 2\*sqrt(a, b)/(a+b), a, b the eigenvalues of M^tM,  
> M transform triangle into equilateral  
>   
> Others  
> 4: Fix the Delaunay condition between two faces  
> 5: Do the flip to improve local topology

`iterations : int = 1`

> *Post optimization relax iter*: number of a planar laplacian smooth iterations that have to be performed after every run

meshing\_invert\_face\_orientation [](#meshing_invert_face_orientation "Link to this definition")

*MeshLab filter name*: ‘Invert Faces Orientation’

Invert faces orientation, flipping the normals of the mesh.  
If requested, it tries to guess the right orientation; mainly it decide to flip all the faces if the minimum/maximum vertices have not outward point normals for a few directions.  
Works well for single component watertight objects.

**Parameters:**

`forceflip : bool = True`

> *Force Flip*: If selected, the normals will always be flipped; otherwise, the filter tries to set them outside

`onlyselected : bool = False`

> *Flip only selected faces*: If selected, only selected faces will be affected

meshing\_isotropic\_explicit\_remeshing [](#meshing_isotropic_explicit_remeshing "Link to this definition")

*MeshLab filter name*: ‘Remeshing: Isotropic Explicit Remeshing’

Perform a explicit remeshing of a triangular mesh, by repeatedly applying edge flip, collapse, relax and refine operations to regularize size and aspect ration of the triangular meshing. Loosely inspired to:  
Hugues Hoppe, Tony DeRose, Tom Duchamp, John McDonald, and Werner Stuetzle.  
Mesh optimization  
(SIGGRAPH '93). ACM, New York, NY, USA, 19–26. [DOI](https://doi.org/10.1145/166117.166119)

**Parameters:**

`iterations : int = 10`

> *Iterations*: Number of iterations of the remeshing operations to repeat on the mesh.

`adaptive : bool = False`

> *Adaptive remeshing*: Toggles adaptive isotropic remeshing.

`selectedonly : bool = False`

> *Remesh only selected faces*: If checked the remeshing operations will be applied only to the selected faces.

`targetlen : PercentageValue = 1%`

> *Target Length*: Sets the target length for the remeshed mesh edges.

`featuredeg : float = 30`

> *Crease Angle*: Minimum angle between faces of the original to consider the shared edge as a feature to be preserved.

`checksurfdist : bool = True`

> *Check Surface Distance*: If toggled each local operation must deviate from original mesh by \[Max. surface distance\]

`maxsurfdist : PercentageValue = 1%`

> *Max. Surface Distance*: Maximal surface deviation allowed for each local operation

`splitflag : bool = True`

> *Refine Step*: If checked the remeshing operations will include a refine step.

`collapseflag : bool = True`

> *Collapse Step*: If checked the remeshing operations will include a collapse step.

`swapflag : bool = True`

> *Edge-Swap Step*: If checked the remeshing operations will include a edge-swap step, aimed at improving the vertex valence of the resulting mesh.

`smoothflag : bool = True`

> *Smooth Step*: If checked the remeshing operations will include a smoothing step, aimed at relaxing the vertex positions in a Laplacian sense.

`reprojectflag : bool = True`

> *Reproject Step*: If checked the remeshing operations will include a step to reproject the mesh vertices on the original surface.

meshing\_merge\_close\_vertices [](#meshing_merge_close_vertices "Link to this definition")

*MeshLab filter name*: ‘Merge Close Vertices’

Merge together all the vertices that are nearer than the specified threshold. Like a unify duplicated vertices but with some tolerance.

**Parameters:**

`threshold : PercentageValue = 1%`

> *Merging distance*: All the vertices that closer than this threshold are merged together. Use very small values, default values is 1/10000 of bounding box diagonal.

meshing\_poly\_to\_tri [](#meshing_poly_to_tri "Link to this definition")

*MeshLab filter name*: ‘Turn into a Pure-Triangular mesh’

Convert into a tri-mesh by splitting any polygonal face.

meshing\_re\_orient\_faces\_by\_geometry [](#meshing_re_orient_faces_by_geometry "Link to this definition")

*MeshLab filter name*: ‘Reorient face normals by geometry’

Reorient face normals by geometry.Given the input mesh, this filter uses raytracing to determine if any faces are pointing inward and corrects their orientation. The number of rays is defined by the user; the higher the number, the higher the precision, but at the cost of computation time.This filter requires two values:
- the number of rays to be shot from the barycenter of each face
- Parity Sampling: If selected, the normal analysis will be performed using the Parity Sampling algorithm. It is suggested to use this algotirhm when the standard one (visibility sampling) faild to riorient all faces because it is used to reorient faces invisible from the outside
**For further details, see the reference paper: Kenshi Takayama, Alec Jacobson, Ladislav Kavan, Olga Sorkine-Hornung.**  
**A Simple Method for Correcting Facet Orientations in Polygon Meshes Based on Ray Casting. Journal of Computer Graphics Techniques 3(4), 2014.** This filter uses the Embree3 library by Intel.

**Parameters:**

`rays : int = 64`

> *Number of rays*: The number of rays shoot from the barycenter of the face. The higher the number the higher the definition of the normal analysis but at the cost of the calculation time

`parity_sampling : bool = False`

> *Parity Sampling*: If checked, the normal analysis will be performed using the parity sampling algorithm. This algorithm is slower than the visibility sampling but works better with some models

meshing\_re\_orient\_faces\_coherently [](#meshing_re_orient_faces_coherently "Link to this definition")

*MeshLab filter name*: ‘Re-Orient all faces coherently’

Re-orient in a consistent way all the faces of the mesh.  
The filter visits a mesh face to face, reorienting any unvisited face so that it is coherent to the already visited faces. If the surface is orientable it will end with a consistent orientation of all the faces. If the surface is not orientable (e.g. it is non manifold or non orientable like a moebius strip) the filter will not build a consistent orientation simply because it is not possible. The filter can end up in a consistent orientation that can be exactly the opposite of the expected one; in that case simply invert the whole mesh orientation.

meshing\_refine\_by\_function [](#meshing_refine_by_function "Link to this definition")

*MeshLab filter name*: ‘Refine User-Defined’

Refine current mesh with user defined parameters.  
Specify a Boolean Function needed to select which edges will be cut for refinement purpose.  
Each edge is identified with first and second vertex.  
Arguments accepted are first and second vertex attributes:  
  
It's possible to use any of the predefined muparser built-in [operators](https://beltoforion.de/en/muparser/features.php#idDef2) and [functions](https://beltoforion.de/en/muparser/features.php#idDef1), like: **&&** (logic and), **||** (logic or), **<**, **<=**, **\>**, **\>=**, **!=** (not equal), **\==** (equal), **\_?\_:\_** (c/c++ ternary operator), and **rnd()** (random value in \[0..1\]), and these values:
- Per-face variables:  
	**fi** (face index), **fr,fg,fb,fa** (face color), **fq** (face quality), **fnx,fny,fnz** (face normal), **fsel** ( 1 if face is selected, 0 if not selected).
- Per-vertex variables:  
	**x0,y0,z0** (first vertex position), **x1,y1,z1** (second vertex position),**x2,y2,z2** (third vertex position), **nx0,ny0,nz0 nx1,ny1,nz1 nx2,ny2,nz2** (vertex normals), **r0,g0,b0,a0 r1,g1,b1,a1 r2,g2,b2,a2** (vertex colors), **vi0, vi1, vi2** (vertex indices), **q0,q1,q2** (vertex quality), **wtu0,wtv0 wtu1,wtv1 wtu2,wtv2** (per-wedge texture coords), **ti** (face texture index), **vsel0,vsel1,vsel2** (1 if vertex is selected, 0 if not).
- Bounding Box variables:  
	**xmin,ymin,zmin** (min coordinates), **xmax,ymax,zmax** (max coordinates), **xmid,ymid,zmid** (midpoint coordinates), **xdim,ydim,zdim** (dimensions), **bbdiag** (diagonal length).
- User-defined attributes:  
	All user defined custom *face scalar attributes* are available. Point3 attribute are available as 3 variables with \_x, \_y, \_z appended to the attribute name.

**Parameters:**

`condselect : str = '(q0 >= 0 && q1 >= 0)'`

> *boolean function*: type a boolean function that will be evaluated on every edge

`x : str = '(x0+x1)/2'`

> *x =*: function to generate x coord of new vertex in \[x0,x1\].  
> For example (x0+x1)/2

`y : str = '(y0+y1)/2'`

> *y =*: function to generate x coord of new vertex in \[y0,y1\].  
> For example (y0+y1)/2

`z : str = '(z0+z1)/2'`

> *z =*: function to generate x coord of new vertex in \[z0,z1\].  
> For example (z0+z1)/2

meshing\_remove\_all\_faces [](#meshing_remove_all_faces "Link to this definition")

*MeshLab filter name*: ‘Delete ALL Faces’

Delete ALL faces, turning the mesh into a pointcloud. May be applied also to all visible layers.

**Parameters:**

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected, the filter will be applied to all visible mesh Layers.

meshing\_remove\_connected\_component\_by\_diameter [](#meshing_remove_connected_component_by_diameter "Link to this definition")

*MeshLab filter name*: ‘Remove Isolated pieces (wrt Diameter)’

Delete isolated connected components whose diameter is smaller than the specified constant

**Parameters:**

`mincomponentdiag : PercentageValue = 10%`

> *Enter max diameter of isolated pieces*: Delete all the connected components (floating pieces) with a diameter smaller than the specified one

`removeunref : bool = True`

> *Remove unfreferenced vertices*: if true, the unreferenced vertices remaining after the face deletion are removed.

meshing\_remove\_connected\_component\_by\_face\_number [](#meshing_remove_connected_component_by_face_number "Link to this definition")

*MeshLab filter name*: ‘Remove Isolated pieces (wrt Face Num.)’

Delete isolated connected components composed by a limited number of triangles

**Parameters:**

`mincomponentsize : int = 25`

> *Enter minimum conn. comp size:*: Delete all the connected components (floating pieces) composed by a number of triangles smaller than the specified one

`removeunref : bool = True`

> *Remove unfreferenced vertices*: if true, the unreferenced vertices remaining after the face deletion are removed.

meshing\_remove\_duplicate\_faces [](#meshing_remove_duplicate_faces "Link to this definition")

*MeshLab filter name*: ‘Remove Duplicate Faces’

Delete all the duplicate faces. Two faces are considered equal if they are composed by the same set of vertices, regardless of the order of the vertices.

meshing\_remove\_duplicate\_vertices [](#meshing_remove_duplicate_vertices "Link to this definition")

*MeshLab filter name*: ‘Remove Duplicate Vertices’

Check for every vertex on the mesh: if there are two vertices with same coordinates they are merged into a single one.

meshing\_remove\_folded\_faces [](#meshing_remove_folded_faces "Link to this definition")

*MeshLab filter name*: ‘Remove Isolated Folded Faces by Edge Flip’

Delete all the single folded faces. A face is considered folded if its normal is opposite to all the adjacent faces. It is removed by flipping it against the face f adjacent along the edge e such that the vertex opposite to e fall inside f

meshing\_remove\_null\_faces [](#meshing_remove_null_faces "Link to this definition")

*MeshLab filter name*: ‘Remove Zero Area Faces’

Remove null faces (the one with area equal to zero)

meshing\_remove\_selected\_faces [](#meshing_remove_selected_faces "Link to this definition")

*MeshLab filter name*: ‘Delete Selected Faces’

Delete the current set of selected faces, vertices that remains unreferenced are not deleted.

meshing\_remove\_selected\_vertices [](#meshing_remove_selected_vertices "Link to this definition")

*MeshLab filter name*: ‘Delete Selected Vertices’

Delete the current set of selected vertices; faces that share one of the deleted vertices are deleted too.

meshing\_remove\_selected\_vertices\_and\_faces [](#meshing_remove_selected_vertices_and_faces "Link to this definition")

*MeshLab filter name*: ‘Delete Selected Faces and Vertices’

Delete the current set of selected faces and all the vertices surrounded by that faces.

meshing\_remove\_t\_vertices [](#meshing_remove_t_vertices "Link to this definition")

*MeshLab filter name*: ‘Remove T-Vertices’

Delete t-vertices from the mesh by edge collapse (collapsing the shortest of the incident edges) or edge flip (flipping the opposite edge on the degenerate face if the triangulation quality improves).

**Parameters:**

`method : str = 'Edge Collapse' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Edge Collapse'`
> > 1. `'Edge Flip'`
> 
> *Method*: Selects whether to remove t-vertices by edge collapse or edge flip.

`threshold : float = 40`

> *Ratio*: Detects faces where the base/height ratio is lower than this value

`repeat : bool = True`

> *Iterate until convergence*: Iterates the algorithm until it reaches convergence

meshing\_remove\_unreferenced\_vertices [](#meshing_remove_unreferenced_vertices "Link to this definition")

*MeshLab filter name*: ‘Remove Unreferenced Vertices’

Check for every vertex on the mesh: if it is NOT referenced by a face, removes it

meshing\_remove\_vertices\_by\_scalar [](#meshing_remove_vertices_by_scalar "Link to this definition")

*MeshLab filter name*: ‘Remove Vertices wrt Quality’

Delete all the vertices with a quality lower smaller than the specified constant

**Parameters:**

`maxqualitythr : PercentageValue = inf%`

> *Delete all vertices with quality under:*:

meshing\_repair\_non\_manifold\_edges [](#meshing_repair_non_manifold_edges "Link to this definition")

*MeshLab filter name*: ‘Repair non Manifold Edges’

Remove non-manifold edges by removing faces (for each non Manifold edge it iteratively deletes the smallest area face until it becomes 2-Manifold) or by splitting vertices (each non manifold edges chain will become a border).

**Parameters:**

`method : str = 'Remove Faces' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Remove Faces'`
> > 1. `'Split Vertices'`
> 
> *Method*: Selects whether to remove non manifold edges by removing faces or by splitting vertices.

meshing\_repair\_non\_manifold\_vertices [](#meshing_repair_non_manifold_vertices "Link to this definition")

*MeshLab filter name*: ‘Repair non Manifold Vertices by splitting’

Split non Manifold vertices until it becomes 2-Manifold.

**Parameters:**

`vertdispratio : float = 0`

> *Vertex Displacement Ratio*: This parameter denote the ratio ⍺ of displacement of a vertex. When a vertex *v* is split, it is moved towards the barycenter *b* of the FF connected faces sharing it of a (*v* - *b*)\*⍺. When ⍺ is zero vertex is not displaced. When ⍺ is 0.5 the new vertex is half away toward the barycenter of the face. Reasonable values are in the \[0.. 0.1\] range.

meshing\_snap\_mismatched\_borders [](#meshing_snap_mismatched_borders "Link to this definition")

*MeshLab filter name*: ‘Snap Mismatched Borders’

Try to snap together adjacent borders that are slightly mismatched.  
This situation can happen on badly triangulated adjacent patches defined by high order surfaces.  
For each border vertex the filter snap it onto the closest boundary edge only if it is closest of *edge\_length\*threshold*. When vertex is snapped the corresponding face is split and a new vertex is created.

**Parameters:**

`edgedistratio : float = 0.01`

> *Edge Distance Ratio*: Collapse edge when the edge / distance ratio is greater than this value. E.g. for default value 1000 two straight border edges are collapsed if the central vertex dist from the straight line composed by the two edges less than a 1/1000 of the sum of the edges length. Larger values enforce that only vertices very close to the line are removed.

`unifyvertices : bool = True`

> *UnifyVertices*: if true the snap vertices are weld together.

meshing\_surface\_subdivision\_butterfly [](#meshing_surface_subdivision_butterfly "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: Butterfly Subdivision’

Apply Butterfly Subdivision Surface algorithm. It is an interpolated refinement method, defined on arbitrary triangular meshes. The scheme is known to be C1 but not C2 on regular meshes  

**Parameters:**

`iterations : int = 3`

> *Iterations*: Number of time the model is subdivided.

`threshold : PercentageValue = 1%`

> *Edge Threshold*: All the edges **longer** than this threshold will be refined.  
> Setting this value to zero will force an uniform refinement.

`selected : bool = False`

> *Affect only selected faces*: If selected the filter affect only the selected faces

meshing\_surface\_subdivision\_catmull\_clark [](#meshing_surface_subdivision_catmull_clark "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: Catmull-Clark’

Apply the Catmull-Clark Subdivision Surfaces. Note that position of the new vertices is simply linearly interpolated. If the mesh is triangle based (no [faux edges](https://stackoverflow.com/questions/59392193)) it generates a quad mesh, otherwise it honores it the faux-edge bits

meshing\_surface\_subdivision\_doo\_sabin [](#meshing_surface_subdivision_doo_sabin "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: Doo Sabin’

Apply the DooSabin Subdivision Surfaces. It is a Dual approximating refinement scheme that creates a new face for each vertex, edge and face. On a pure quad mesh it will add non quad face for each extraordinarhy vertex in the mesh (e.g. in a cube it will add a triangular face for each corner. On the other hand after a refinement step all the vertices will have degree 4.

**Parameters:**

`iterations : int = 2`

> *Iterations*: Number of times the model is subdivided.

meshing\_surface\_subdivision\_loop [](#meshing_surface_subdivision_loop "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: Loop’

Apply Loop's Subdivision Surface algorithm. It is an approximant refinement method and it works for every triangle and has rules for extraordinary vertices.  

**Parameters:**

`loopweight : str = 'Loop' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Loop'`
> > 1. `'Enhance regularity'`
> > 2. `'Enhance continuity'`
> 
> *Weighting scheme*: Change the weights used. Allows one to optimize some behaviors over others.

`iterations : int = 3`

> *Iterations*: Number of time the model is subdivided.

`threshold : PercentageValue = 1%`

> *Edge Threshold*: All the edges **longer** than this threshold will be refined.  
> Setting this value to zero will force an uniform refinement.

`selected : bool = False`

> *Affect only selected faces*: If selected the filter affect only the selected faces

meshing\_surface\_subdivision\_ls3\_loop [](#meshing_surface_subdivision_ls3_loop "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: LS3 Loop’

Apply LS3 Subdivision Surface algorithm using Loop's weights. This refinement method take normals into account.  
See:*Boye', S. Guennebaud, G. & Schlick, C.*  
**Least squares subdivision surfaces**  
Computer Graphics Forum, 2010.  
  
Alternatives weighting schemes are based on the paper: *Barthe, L. & Kobbelt, L.*  
**Subdivision scheme tuning around extraordinary vertices**  
Computer Aided Geometric Design, 2004, 21, 561-583.  
The current implementation of these schemes don't handle vertices of valence > 12

**Parameters:**

`loopweight : str = 'Loop' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Loop'`
> > 1. `'Enhance regularity'`
> > 2. `'Enhance continuity'`
> 
> *Weighting scheme*: Change the weights used. Allows one to optimize some behaviors over others.

`iterations : int = 3`

> *Iterations*: Number of time the model is subdivided.

`threshold : PercentageValue = 1%`

> *Edge Threshold*: All the edges **longer** than this threshold will be refined.  
> Setting this value to zero will force an uniform refinement.

`selected : bool = False`

> *Affect only selected faces*: If selected the filter affect only the selected faces

meshing\_surface\_subdivision\_midpoint [](#meshing_surface_subdivision_midpoint "Link to this definition")

*MeshLab filter name*: ‘Subdivision Surfaces: Midpoint’

Apply a plain subdivision scheme where every edge is split on its midpoint. Useful to uniformly refine a mesh substituting each triangle with four smaller triangles.

**Parameters:**

`iterations : int = 3`

> *Iterations*: Number of time the model is subdivided.

`threshold : PercentageValue = 1%`

> *Edge Threshold*: All the edges **longer** than this threshold will be refined.  
> Setting this value to zero will force an uniform refinement.

`selected : bool = False`

> *Affect only selected faces*: If selected the filter affect only the selected faces

meshing\_tri\_to\_quad\_by\_4\_8\_subdivision [](#meshing_tri_to_quad_by_4_8_subdivision "Link to this definition")

*MeshLab filter name*: ‘Tri to Quad by 4-8 Subdivision’

Convert a tri mesh into a quad mesh by applying a 4-8 subdivision scheme.It introduces less overhead than the plain Catmull-Clark Subdivision Surfaces(it adds only a single vertex for each triangle instead of four).  
See:  
**4-8 Subdivision**  
*Luiz Velho, Denis Zorin*  
CAGD, volume 18, Issue 5, Pages 397-427.

meshing\_tri\_to\_quad\_by\_smart\_triangle\_pairing [](#meshing_tri_to_quad_by_smart_triangle_pairing "Link to this definition")

*MeshLab filter name*: ‘Tri to Quad by smart triangle pairing’

Convert a tri-mesh into a quad mesh by pairing triangles.

meshing\_tri\_to\_quad\_dominant [](#meshing_tri_to_quad_dominant "Link to this definition")

*MeshLab filter name*: ‘Turn into Quad-Dominant mesh’

Convert a tri-mesh into a quad-dominant mesh by pairing suitable triangles.

**Parameters:**

`level : str = 'Fewest triangles' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Fewest triangles'`
> > 1. `'(in between)'`
> > 2. `'Better quad shape'`
> 
> *Optimize For:*: Choose any of three different greedy strategies.

meshing\_vertex\_attribute\_seam [](#meshing_vertex_attribute_seam "Link to this definition")

*MeshLab filter name*: ‘Vertex Attribute Seam’

Make all selected vertex attributes connectivity-independent:  
vertices are duplicated whenever two or more selected wedge or face attributes do not match.  
This is particularly useful for GPU-friendly mesh layout, where a single index must be used to access all required vertex attributes.

**Parameters:**

`normalmode : str = 'None' (or int = 0)`

> Possible enum values:
> 
> > 0. `'None'`
> > 1. `'Vertex'`
> > 2. `'Wedge'`
> > 3. `'Face'`
> 
> *Normal Source:*: Choose a method

`colormode : str = 'None' (or int = 0)`

> Possible enum values:
> 
> > 0. `'None'`
> > 1. `'Vertex'`
> > 2. `'Wedge'`
> > 3. `'Face'`
> 
> *Color Source:*: Choose a method

`texcoordmode : str = 'None' (or int = 0)`

> Possible enum values:
> 
> > 0. `'None'`
> > 1. `'Vertex'`
> > 2. `'Wedge'`
> 
> *Texcoord Source:*: Choose a method

nxs\_build [](#nxs_build "Link to this definition")

*MeshLab filter name*: ‘NXS Build’

[Nexus](http://vcg.isti.cnr.it/nexus/) is set of c++/javascript libraries and tools for the creation and efficient visualization of multiresolution 3D models. Nexus it is tailored for the processing and the streaming visualization of very large unstructured 3d modelslike the ones coming from 3D scanning.  
This filter is the equivalent of calling [nxsbuild](http://vcg.isti.cnr.it/nexus/#nxsbuild): it creates a nxs file starting from a file containing a 3D object, without the need of loading it before. It supports only the following 3D formats: obj, ply or stl.

**Parameters:**

`input_file : str = ''`

> *Input File*: The input file from which create the.nxs file.

`output_file : str = ''`

> *Output File*: The name of the output nxs file.

`node_faces : int = 32768`

> *Node faces*: Number of faces per patch, (min ~1000, max 32768)  
> This parameter controls the granularity of the multiresolution: smaller values result in smaller changes (less 'pop').Small nodes are less efficient in rendering and compression.  
> Meshes with very large textures and few vertices benefit from small nodes.

`top_node_faces : int = 4096`

> *Top node faces*: Number of triangles in the top node. Controls the size of the smallest LOD. Higher values will delay the first rendering but with higher quality.

`tex_quality : int = 95`

> *JPEG texture quality \[0-100\]*: jpg texture quality

`ram : int = 2000`

> *Ram buffer*: Max ram used in MegaBytes (WARNING: just an approximation)

`skiplevels : int = 0`

> *Skip levels*: Decimation skipped for n levels. Use for meshes with large textures and very few vertices.

`origin : numpy.ndarray[numpy.float64[3]] = [0, 0, 0]`

> *Origin*: new origin for the model

`center : bool = False`

> *Center*: Set origin in the bounding box center

`pow_2_textures : bool = False`

> *Pow 2 textures*: Create textures to be power of 2

`deepzoom : bool = False`

> *Deepzoom*: Save each node and texture to a separated file. Used for server which do not support http range requests (206). Will generate MANY files.

`adaptive : float (bounded) = 0.333 [min: 0; max: 1]`

> *Adaptive*: Split nodes adaptively. Different settings might help with very uneven distribution of geometry.

nxs\_compress [](#nxs_compress "Link to this definition")

*MeshLab filter name*: ‘NXS Compress’

[Nexus](http://vcg.isti.cnr.it/nexus/) is set of c++/javascript libraries and tools for the creation and efficient visualization of multiresolution 3D models. Nexus it is tailored for the processing and the streaming visualization of very large unstructured 3d modelslike the ones coming from 3D scanning.  
This filter is the equivalent of calling nxscompress, which creates a.nxz (compressed nexus) file starting from a file.nxs (uncompressed nxs). It is useful for exploring different lossy compression settings without the need of recreating the whole multiresolution structure.

**Parameters:**

`input_file : str = ''`

> *Input File*: The input nxs file to compress into an nxz file.

`output_file : str = ''`

> *Output File*: The name of the output nxz file.

`nxz_vertex_quantization : float = 0`

> *NXZ Vertex quantization*: absolute side of quantization grid (uses quantization factor, instead)

`vertex_bits : int = 0`

> *Vertex bits*: number of bits in vertex coordinates when compressing (uses quantization factor, instead)

`quantization_factor : float = 0.1`

> *Quantization factor*: Quantization as a factor of error

`luma_bits : int = 6`

> *Luma bits*: Quantization of luma channel

`chroma_bits : int = 6`

> *Chroma bits*: Quantization of chroma channel

`alpha_bits : int = 5`

> *Alpha bits*: Quantization of alpha channel

`normal_bits : int = 10`

> *Normal bits*: Quantization of normals

`textures_precision : float = 0.25`

> *Textures precision*: Quantization of textures, precision in pixels per unit

raster\_alignment\_mutual\_information [](#raster_alignment_mutual_information "Link to this definition")

*MeshLab filter name*: ‘Image alignment: Mutual Information’

Register an image on a 3D model using Mutual Information. This filter is an implementation of Corsini et al. 'Image-to-geometry registration: a mutual information method exploiting illumination-related geometric properties', 2009, [Get link](http://vcg.isti.cnr.it/Publications/2009/CDPS09/)

**Parameters:**

`rendering_mode : str = 'Combined' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Combined'`
> > 1. `'Normal map'`
> > 2. `'Color per vertex'`
> > 3. `'Specular'`
> > 4. `'Silhouette'`
> > 5. `'Specular combined'`
> 
> *Rendering mode:*: Rendering modes

`shot : Shotf [still unsupported] = None`

> *Starting shot*: If the point of view has been set by hand, it must be retrieved from current trackball

`estimate_focal : bool = False`

> *Estimate focal length*: Estimate focal length: if not checked, only extrinsic parameters are estimated

`fine : bool = True`

> *Fine Alignment*: Fine alignment: the perturbations applied to reach the alignment are smaller

`numofiterations : int = 100`

> *Max iterations*: Maximum number of iterations

`tolerance : float = 0.1`

> *Tolerance*: Threshold to stop convergence

`expectedvariance : float = 2`

> *Expected Variance*: Expected Variance

`backgroundweight : int = 2`

> *Background Weight*: Weight of background pixels (1, as all the other pixels; 2, one half of the other pixels etc etc)

raster\_global\_refinement\_mutual\_information [](#raster_global_refinement_mutual_information "Link to this definition")

*MeshLab filter name*: ‘Image Registration: Global refinement using Mutual Information’

Calculate a global refinement of image registration, in order to obtain a better alignment of fine detail. It will refine only the shots associated to the active rasters, the non-active ones will be used but not refined. This filter is an implementation of Dellepiane et al. 'Global refinement of image-to-geometry registration for color projection', 2013, and it was used in Corsini et al 'Fully Automatic Registration of Image Sets on Approximate Geometry', 2013. Please cite!

**Parameters:**

`renderingmode : str = 'Combined' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Combined'`
> > 1. `'Normal map'`
> > 2. `'Color per vertex'`
> > 3. `'Specular'`
> > 4. `'Silhouette'`
> > 5. `'Specular combined'`
> 
> *Rendering mode:*: Rendering modes

`max_number_of_refinement_steps : int = 5`

> *Maximum number of minimizations step*: Maximum number of minimizations step on the global graph

`threshold_for_refinement_convergence : float = 1.2`

> *Threshold for refinement convergence (in pixels)*: The threshold (average quadratic variation in the projection on image plane of some samples of the mesh before and after each step of refinement) that stops the refinement

`pre_alignment : bool = False`

> *Pre-alignment step*: Pre-alignment step

`estimate_focal : bool = True`

> *Estimate focal length*: Estimate focal length

`fine : bool = True`

> *Fine Alignment*: Fine alignment

save\_active\_raster\_cameras [](#save_active_raster_cameras "Link to this definition")

*MeshLab filter name*: ‘Export active rasters cameras to file’

Export active cameras to file, in the.out or Agisoft.xml formats

**Parameters:**

`exportfile : str = 'Bundler .out' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Bundler .out'`
> > 1. `'Agisoft xml'`
> 
> *Output format*: Choose the output format, The filter enables to export the cameras to both Bundler and Agisoft Photoscan.

`newname : str = 'cameras'`

> *Export file name (the right extension will be added at the end)*: Name of the output file, it will be saved in the same folder as the project file.

save\_snapshot [](#save_snapshot "Link to this definition")

*MeshLab filter name*: ‘GPU Filter Example’

Small useless filter added only to show how to work with a gl render context inside a filter.

**Parameters:**

`imagebackgroundcolor : Color = [50; 50; 50; 255]`

> *Image Background Color*: The color used as image background.

`imagewidth : int = 512`

> *Image Width*: The width in pixels of the produced image.

`imageheight : int = 512`

> *Image Height*: The height in pixels of the produced image.

`imagefilename : str = 'gpu_generated_image.png'`

> *Base Image File Name*: The file name used to save the image.

set\_camera\_per\_mesh [](#set_camera_per_mesh "Link to this definition")

*MeshLab filter name*: ‘Set Mesh Camera’

This filter allows one to set a shot for the current mesh

**Parameters:**

`shot : Shotf [still unsupported] = None`

> *New shot*: This filter allows one to set a shot for the current mesh.

set\_camera\_per\_raster [](#set_camera_per_raster "Link to this definition")

*MeshLab filter name*: ‘Set Raster Camera’

This filter allows one to set a shot for the current mesh

**Parameters:**

`shot : Shotf [still unsupported] = None`

> *New shot*: This filter allows one to set a shot for the current raster.

set\_color\_per\_vertex [](#set_color_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Color Filling’

Fills the color of the vertices of the mesh with a color chosen by the user.

**Parameters:**

`color1 : Color = [0; 0; 0; 255]`

> *Color:*: Sets the color to apply to vertices.

`onselected : bool = False`

> *Only on selection*: If checked, only affects selected vertices

set\_matrix [](#set_matrix "Link to this definition")

*MeshLab filter name*: ‘Matrix: Set/Copy Transformation’

Set the current transformation matrix by filling it, or copying from another layer.

**Parameters:**

`transformmatrix : numpy.ndarray[numpy.float64[4, 4]] = [[1, 0, 0, 0],[0, 1, 0, 0],[0, 0, 1, 0],[0, 0, 0, 1]]`

> :

`compose : bool = False`

> *Compose with current*: If selected, the new matrix will be composed with the current one (matrix=new\*old)

`freeze : bool = True`

> *Freeze Matrix*: The transformation is explicitly applied, and the vertex coordinates are actually changed

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected, the filter will be applied to all visible mesh layers

set\_matrix\_identity [](#set_matrix_identity "Link to this definition")

*MeshLab filter name*: ‘Matrix: Reset Current Matrix’

Set the current transformation matrix to the Identity.

**Parameters:**

`alllayers : bool = False`

> *Apply to all visible Layers*: If selected the filter will be applied to all visible mesh layers

set\_mesh\_name [](#set_mesh_name "Link to this definition")

*MeshLab filter name*: ‘Rename Current Mesh’

Explicitly change the label shown for a given mesh

**Parameters:**

`newname : str = 'cube'`

> *New Label*: New Label for the mesh.

set\_raster\_name [](#set_raster_name "Link to this definition")

*MeshLab filter name*: ‘Rename Current Raster’

Explicitly change the label shown for a given raster

**Parameters:**

`newname : str = ''`

> *New Label*: New Label for the raster.

set\_selection\_all [](#set_selection_all "Link to this definition")

*MeshLab filter name*: ‘Select All’

Select all the faces/vertices of the current mesh.

**Parameters:**

`allfaces : bool = True`

> *Select all Faces*: If true the filter will select all the faces.

`allverts : bool = True`

> *Select all Vertices*: If true the filter will select all the vertices.

set\_selection\_none [](#set_selection_none "Link to this definition")

*MeshLab filter name*: ‘Select None’

Clear the current set of selected faces/vertices.

**Parameters:**

`allfaces : bool = True`

> *De-select all Faces*: If true the filter will de-select all the faces.

`allverts : bool = True`

> *De-select all Vertices*: If true the filter will de-select all the vertices.

set\_texture\_per\_mesh [](#set_texture_per_mesh "Link to this definition")

*MeshLab filter name*: ‘Set Texture’

Set a texture associated with current mesh parametrization.  
If the texture provided exists, then it will be simply associated to the current mesh; else the filter will fail with no further actions.

**Parameters:**

`textname : str = ''`

> *Texture file*: Sets the given input image as unique texture of the mesh.

`use_dummy_texture : bool = False`

> *Use dummy texture*: If checked, the filter will set a dummy texture instead of loading an image. The 'Texture File' parameter will be ignored.

transfer\_attributes\_per\_vertex [](#transfer_attributes_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Vertex Attribute Transfer’

Transfer the chosen per-vertex attributes from one layer to another. Useful to transfer attributes to different representations of a same object.  
For each vertex of the target mesh the closest point (not vertex!) on the source mesh is computed, and the requested interpolated attributes from that source point are copied into the target vertex.  
The algorithm assumes that the two meshes are reasonably similar and aligned.

**Parameters:**

`sourcemesh : int = 0`

> *Source Mesh*: The mesh that contains the source data that we want to transfer.

`targetmesh : int = 0`

> *Target Mesh*: The mesh whose vertices will receive the data from the source.

`vertexsampling : bool = False`

> *Vertex Sampling*: if enabled for each vertex of the target mesh we search the closest vertex in the source mesh and directly copy the found attributes, otherwise we search for the closest point on the source surface that usually falls inside a face and attribute are therefore interpolated

`geomtransfer : bool = False`

> *Transfer Geometry*: if enabled, the position of each vertex of the target mesh will be snapped onto the corresponding closest point on the source mesh

`normaltransfer : bool = False`

> *Transfer Normal*: if enabled, the normal of each vertex of the target mesh will get the (interpolated) normal of the corresponding closest point on the source mesh

`colortransfer : bool = True`

> *Transfer Color*: if enabled, the color of each vertex of the target mesh will become the color of the corresponding closest point on the source mesh

`qualitytransfer : bool = False`

> *Transfer quality*: if enabled, the quality of each vertex of the target mesh will become the quality of the corresponding closest point on the source mesh

`selectiontransfer : bool = False`

> *Transfer Selection*: if enabled, each vertex of the target mesh will be selected if the corresponding closest point on the source mesh falls in a selected face

`qualitydistance : bool = False`

> *Store dist. as quality*: if enabled, we store the distance of the transferred value as in the vertex quality

`savebarycentric : bool = False`

> *Save barycentric coords*: if enabled, we store as per vertex attributes of the target mesh, the index of the closest face and the barycentric coordinates of its position inside that face of the src mesh. If vertex sampling is enabled or if source mesh is a point cloud, only the index of the corresponding closest vertex on the src is saved.

`upperbound : PercentageValue = 2%`

> *Max Dist Search*: Sample points for which we do not find anything within this distance are rejected and not considered for recovering attributes.

`onselected : bool = False`

> *Only on selection*: If checked, only transfer to selected vertices on TARGET mesh

transfer\_attributes\_to\_texture\_per\_vertex [](#transfer_attributes_to_texture_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Transfer: Vertex Attributes to Texture (1 or 2 meshes)’

Transfer texture color, vertex color or normal from one mesh the texture of another mesh. This may be useful to restore detail lost in simplification, or resample a texture in a different parametrization.

**Parameters:**

`sourcemesh : int = 0`

> *Source Mesh*: The mesh that contains the source data that we want to transfer

`targetmesh : int = 0`

> *Target Mesh*: The mesh whose texture will be filled according to source mesh data

`attributeenum : str = 'Vertex Color' (or int = 0)`

> Possible enum values:
> 
> > 0. `'Vertex Color'`
> > 1. `'Vertex Normal'`
> > 2. `'Vertex Quality'`
> > 3. `'Texture Color'`
> 
> *Color Data Source*: Choose what attribute has to be transferred onto the target texture. You can choose between Per vertex attributes (color,normal,quality) or to transfer color information from source mesh texture

`upperbound : PercentageValue = 2%`

> *Max Dist Search*: Sample points for which we do not find anything within this distance are rejected and not considered for recovering data

`textname : str = 'texture.png'`

> *Texture file*: The texture file to be created

`textw : int = 1024`

> *Texture width (px)*: The texture width

`texth : int = 1024`

> *Texture height (px)*: The texture height

`overwrite : bool = False`

> *Overwrite Target Mesh Texture*: if target mesh has a texture will be overwritten (with provided texture dimension)

`pullpush : bool = True`

> *Fill texture*: if enabled the unmapped texture space is colored using a pull push filling algorithm, if false is set to black

transfer\_iso\_parametrization\_between\_meshes [](#transfer_iso_parametrization_between_meshes "Link to this definition")

*MeshLab filter name*: ‘Iso Parametrization transfer between meshes’

Transfer the Isoparametrization between two meshes, the two meshes must be reasonably similar and well aligned. It is useful to transfer back an isoparam onto the original mesh after having computed it on a dummy, clean watertight model.  
For more details see:  
**N. Pietroni, M. Tarini and P. Cignoni**,  
['Almost isometric mesh parameterization through abstract domains'](http://vcg.isti.cnr.it/Publications/2010/PTC10/)  
IEEE Transaction of Visualization and Computer Graphics, 2010

**Parameters:**

`sourcemesh : int = 0`

> *Source Mesh*: The mesh already having an Isoparameterization

`targetmesh : int = 0`

> *Target Mesh*: The mesh to be Isoparameterized

transfer\_texture\_to\_color\_per\_vertex [](#transfer_texture_to_color_per_vertex "Link to this definition")

*MeshLab filter name*: ‘Transfer: Texture to Vertex Color (1 or 2 meshes)’

Generates Vertex Color values picking color from a texture (same mesh or another mesh).

**Parameters:**

`sourcemesh : int = 0`

> *Source Mesh*: The mesh with associated texture that we want to sample from

`targetmesh : int = 0`

> *Target Mesh*: The mesh whose vertex color will be filled according to source mesh texture

`upperbound : PercentageValue = 2%`

> *Max Dist Search*: Sample points for which we do not find anything within this distance are rejected and not considered for recovering color