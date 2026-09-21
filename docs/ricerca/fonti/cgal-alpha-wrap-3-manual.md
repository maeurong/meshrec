CGAL 6.2.1 - 3D Alpha Wrapping

Searching...

No Matches

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_bike_lod.jpg)

Note: a two-dimensional version of this package is also available: [2D Alpha Wrapping](https://doc.cgal.org/latest/Manual/packages.html#PkgAlphaWrap2).

## Introduction

Various tasks in geometric modeling and processing require 3D objects represented as valid surface meshes, where "valid" refers to meshes that are watertight, intersection-free, orientable, and 2-manifold. Such representations offer well-defined notions of interior/exterior and geodesic neighborhoods.

3D data are usually acquired through measurements followed by reconstruction, designed by humans, or generated through imperfect automated processes. As a result, they can exhibit a wide variety of defects including gaps, missing data, self-intersections, degeneracies such as zero-volume structures, and non-manifold features.

Given the large repertoire of possible defects, many methods and data structures have been proposed to repair specific defects, usually with the goal of guaranteeing specific properties in the repaired 3D model. Reliably repairing all types of defects is notoriously difficult and is often an ill-posed problem as many valid solutions exist for a given 3D model with defects. In addition, the input model can be overly complex with unnecessary geometric details, spurious topological structures, nonessential inner components, or excessively fine discretizations. For applications such as collision avoidance, path planning, or simulation, getting an approximation of the input can be more relevant than repairing it. Approximation herein refers to an approach capable of filtering out inner structures, fine details and cavities, as well as wrapping the input within a user-defined offset margin.

Given an input 3D geometry, we address the problem of computing a conservative approximation, where conservative means that the output is guaranteed to strictly enclose the input. We seek unconditional robustness in the sense that the output mesh should be valid (oriented, 2-manifold, and without self-intersections), even for raw input with many defects and degeneracies. The default input is a soup of 3D triangles, but the generic interface leaves the door open to other types of finite 3D primitives such as triangle soups and point sets.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_triangle_soup.jpg)

[Figure 68.1](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_input_1_fig) Shrink-wrapping output from a triangle soup, with many intersections and gaps. From left to right, input model, output wrap, and superposition.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_non_manifold_cases.jpg)

[Figure 68.2](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_input_2_fig) Dealing with non-manifold features and degeneracies. From left to right, a non-manifold vertex, self-intersecting faces and two adjacent triangles representing a zero-volume structure. The algorithm handles these cases by wrapping an offset of the input.

## Approach

Many approaches have been devised to enclose a 3D model within a volume, featuring different balances between the runtime and quality (i.e., tightness) of the approximation. Within the simplest cases, an axis-aligned or oriented bounding box clearly satisfies some desired properties; however, the approximation error is uncontrollable and often very large. Computing the convex hull of the input also matches some of the desired properties and improves the quality of the result, albeit at the price of increasing the runtime. However, the approximation remains crude, especially in the case of several components.

The convex hull is, in fact, a special case of alpha shapes ([Chapter\_3D\_Alpha\_Shapes](https://doc.cgal.org/latest/Alpha_shapes_3/index.html#Chapter_3D_Alpha_Shapes)). Mathematically, the alpha shape is a subcomplex of the Delaunay triangulation, with simplicies being part of the complex depending on the size of their minimal (empty) Delaunay ball. Intuitively, constructing 3D alpha shapes can be thought of as carving 3D space with an empty ball of user-defined radius alpha. Alpha shapes yield provable, good piecewise-linear approximations of a shape [\[1\]](https://doc.cgal.org/latest/Alpha_wrap_3/citelist.html#CITEREF_bb-srmua-97t), but are defined on point sets, whereas we wish to deal with more general input data, such as triangle soups. Even after sampling the triangle soup, alpha shapes do not guarantee to be conservative for any alpha. Finally, inner structures are also carved within the volumes, instead of being filtered out.

Inspired by alpha shapes, we replace the above notion of carving by *shrink-wrapping*: we iteratively construct a subcomplex of a 3D Delaunay triangulation by starting from a simple 3D Delaunay triangulation enclosing the input, and then iteratively removing eligible tetrahedra that lie on the boundary of the complex. In addition, the underlying triangulation—and thus the complex incidentally—is refined as shrinking proceeds. Thus, instead of carving from the convex hull of the input data as in alpha shapes, we construct an entirely new mesh through a Delaunay refinement-like algorithm. The refinement algorithm inserts Steiner points on the boundary of an offset volume, defined as a level set of the unsigned distance field to the input.

This process both prevents the creation of inner structures within the output and avoids superfluous computations. In addition, detaching our mesh construction from the geometry and discretization of the input has several advantages: (1) the underlying data is not restricted to a specific format (triangle soups, polygon soups, point clouds, etc.) as all that is required is answering three basic geometric queries: (a) the distance between a point and the input, (b) the projection of a query point onto the input, (c) an intersection test between a tetrahedron and the input, and (2) The user has more freedom to trade tightness to the input for final mesh complexity, as constructing a conservative approximation on a large offset of the input requires fewer mesh elements.

## Algorithm

**Initialization**. The algorithm is initialized by inserting the eight corner vertices of a loose bounding box into a 3D Delaunay triangulation. In the 3D Delaunay triangulation of CGAL, all triangle facets are adjacent to two tetrahedron cells. Each facet of the boundary of the Delaunay triangulation, which coincides with one facet of the convex hull of the triangulation vertices, is adjacent to a so-called *infinite* tetrahedron cell, an abstract cell connected to the so-called *infinite vertex* to ensure the aforementioned double-facet adjacency. Initially, all infinite cells are tagged as outside, and all finite tetrahedron cells are tagged as inside.

**Shrink-wrapping**. The shrink-wrapping algorithm proceeds by traversing the cells of the Delaunay triangulation from outside to inside, flood-filling from one cell to its adjacent cell, and tagging the adjacent cell as outside whenever possible (the term possible is specified later). Flood filling is implemented via a priority queue of Delaunay triangle facets representing the traversal between the two adjacent cells of the facet, from outside to inside. These triangle facets are referred to as *gates* in the following.

Given an outside cell and its adjacent inside cell, the common facet (i.e., a gate) is said to be *alpha-traversable* if its circumradius is larger than the user-defined parameter alpha, where circumradius refers to the radius of the relating triangle's Delaunay ball. Intuitively, cavities smaller than alpha are not accessible as their gates are not alpha-traversable.

Initialized by the alpha-traversable gates on the convex hull, the priority queue contains only alpha-traversable gates and is sorted by decreasing order of the circumradius of the gate. Traversal can be seen as a continuous process that advances along dual Voronoi edges of the gates, with a pencil of empty balls circumscribing the gate.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_pencil.png)

[Figure 68.3](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_pencil_fig) (Left) Pencil of empty circles (blue) circumscribing a Delaunay edge (green) in a 2D Delaunay triangulation (black). From the top triangle circumcenter *c1* to the bottom triangle circumcenter *c2*, the dual Voronoi edge denoted by *e* (doted red) is the trace of centers of the largest circles that are empty of Delaunay vertex. (Right) The graph corresponding to the left example. The x-axis corresponds to the position of empty circle centers located on the Voronoi edge *e*, from *c1* to *c2*. The y-axis is the radius value of the corresponding empty circles. In this case, the minimum radius of this pencil of empty circle is located at the midpoint of the green Delaunay edge. In our algorithm, a gate (green Delaunay edge) is said to be not alpha-traversable when the minimum radius of the pencil of empty circle is smaller than alpha.

When traversing from an outside cell $c_o$ to an inside cell $c_i$ through an alpha-traversable facet $f$, two criteria are tested to prevent the wrapping process from colliding with the input:

(1) We check for an intersection between the dual Voronoi edge of $f$, i.e. the segment between the circumcenters of the two incident cells, and the *offset surface*, defined as the level set of unsigned isosurface to the input. If one or several intersections exists, the first intersection point, along the dual Voronoi edge oriented from outside to inside is inserted into the triangulation as a Steiner point.

(2) If the dual Voronoi edge does not intersect the offset surface but the neighboring cell $c_i$ intersects the input, we compute the projection of the circumcenter of $c_i$ onto the offset surface, and insert it into the triangulation as a Steiner point (which destroys $c_i$).

After each of the above Steiner point insertions, all new incident cells are tagged as inside, and the newly alpha-traversable gates are pushed into the priority queue.

If none of the above two criteria are met, the neighboring cell $c_i$ is traversed and tagged as outside. Alpha-Traversable facets of $c_i$ that are separating inside from outside cells are pushed as new gates into the priority queue.

Once the queue empties—a process that is guaranteed as facets (and their circumradii) become smaller due to the insertion of new Steiner points—the construction phase terminates. The output triangle surface mesh is extracted from the Delaunay triangulation as the set of facets separating inside from outside cells.

The figure below depicts the steps of the algorithm in 2D.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_steps.jpg)

[Figure 68.4](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_steps_fig) Steps of the shrink-wrapping algorithm in 2D. The algorithm is initialized by inserting the corners of the loose bounding box of the input (red) into a Delaunay triangulation, and all finite triangles are tagged inside (grey). The current gate (green edge) popped out from the queue is alpha-traversable. The triangle adjacent to the gate is tagged outside when it does not intersect the input, and new alpha-traversable gates are pushed to the queue. When the adjacent triangle intersects the input, a new Steiner point (large green disc) is computed and inserted into the triangulation, all neighboring triangles are tagged inside, new alpha-traversable gates are pushed to the queue, and traversal is resumed. Grey edges depict the Delaunay triangulation. Blue edges depict the Voronoi diagram. Pink circles depict the empty circle of radius alpha. The output edges (dark blue) separate inside from outside triangles.

## Guarantees

The algorithm is proven to terminate and to produce a 2-manifold triangulated surface mesh that strictly encloses the input data. The key element to the proof is that we wrap from outside to inside and never allow a cell that intersects the input to be flagged outside. Furthermore, both criteria that lead to refinement of the triangulation insert Steiner points that are guaranteed to break the cells in need of refinement and reduce the neighbor facets circumradii.

Because the main refinement criterion is the insertion of an intersection between a dual Voronoi edge and an offset of the input, or the projection of a Voronoi vertex onto the offset of the input, the algorithm has similarities to popular meshing algorithms based on Delaunay filtering and refinement (see [Chapter\_3D\_Mesh\_Generation](https://doc.cgal.org/latest/Mesh_3/index.html#Chapter_3D_Mesh_Generation)).

## Interface

Our algorithm takes as input a set of triangles in 3D, provided either as a triangle soup or as a triangle surface mesh, and two user-defined scalar parameters: the *alpha* and the *offset* values. It proceeds by shrink-wrapping and refining a 3D Delaunay triangulation starting from a loose bounding box of the input. The parameter *alpha* refers to the size of cavities or holes that cannot be traversed during wrapping, and hence to the final level of detail, as alpha acts like a sizing field in a common Delaunay refinement algorithm ([Chapter\_3D\_Mesh\_Generation](https://doc.cgal.org/latest/Mesh_3/index.html#Chapter_3D_Mesh_Generation)). The parameter *offset* refers to the distance between the vertices of the refined triangulation and the input, so that a large offset translates into a loose enclosing of the input. This second parameter offers a means to control the trade-off between tightness and complexity.

The main entry point of the component is the global function `CGAL::alpha_wrap_3()` that generates the alpha wrap; this function takes as input a polygon soup or a polygon mesh. There is no prerequisite on the input connectivity so that it can take an arbitrary triangle soup, with islands, self-intersections, or overlaps, as well as combinatorial or geometrical degeneracies.

The underlying traits class must be a model of the `Kernel` concept. It should use a floating point number type as inexactness is inherent to the algorithm since there is no closed form description of new vertices on the offset surface.

The output is a triangle surface mesh whose type is chosen by the user, under the constraint that it must be a model of the `MutableFaceGraph` concept.

## Choosing Parameters

The two parameters of the algorithm impact both the level of detail and complexity of the output mesh.

## Alpha

The main parameter, alpha, controls whether a Delaunay facet is traversable during shrink-wrapping. Alpha's main purpose is to control the size of the empty balls used during wrapping, and thus to determine which features will appear in the output: indeed, a facet is alpha-traversable if its circumradius is larger than alpha; hence, the algorithm can only shrink-wrap through straits or holes with diameters larger than alpha. A second, less direct consequence is that as long as a facet has a circumradius larger than alpha, the incident inside cell will be visited and possibly refined. Therefore, when the algorithm terminates, all facets have a circumradius smaller than alpha. This parameter thus also behaves like a sizing criterion on the triangle facets of the output.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_church_lod.jpg)

[Figure 68.5](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_alpha_param_fig) Impact of the alpha parameter on the output. (Left) The input triangle mesh, generated by surface reconstruction from a raw point cloud, has many non-manifold edges and vertices, superfluous geometric details and spurious topological structures. (Right) This component approximates the input conservatively and produces valid meshes with different complexity and fidelity to the input, depending on the alpha parameter. The smaller the alpha, the deeper the shrink-wrapping process will enter cavities. The alpha parameter is decreasing from left to right, to respectively 1/50, 1/100 and 1/300 of the longest diagonal of the input bounding box. A large alpha will produce an output less complex but less faithful to the input.

## Offset

The second parameter, the offset distance, controls the distance from the input and thus the definition of the offset isosurface onto which the vertices of the output mesh are located. This parameter controls the tightness of the result, which has, in turn, a few consequences. Firstly, locating vertices away from the input enables the algorithm to generate a less complex mesh, especially in convex areas. A trivial example of this behavior would be a very dense mesh of a sphere, for which an as-tight-as-possible envelope would also be very dense. Secondly, the farther the isosurface is from the input, the more new points are inserted through the first criterion (i.e., through intersection with dual Voronoi edge, see Section [Algorithm](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#aw3_algorithm)); thus, the quality of the output improves in terms of angles of the triangle elements. Finally, and depending on the value of the alpha parameter, a large offset can also offer defeaturing capabilities. However, using a small offset parameter will tend to better preserve sharp features as projection Steiner points tend to project onto convex sharp features.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_sharp_feature.jpg)

[Figure 68.6](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_offset_param_fig) Impact of the offset parameter on the output. (Left) Input mesh generated by meshing a NURBS CAD model in parameter space. (Right) The smaller the offset, the closest sample points are to the input. The offset parameter is decreasing from left to right, to respectively 1/50, 1/200 and 1/1000 of the longest diagonal of the input bounding box. The alpha parameter is equal to 1/50 of the longest diagonal of the input bounding box for all level of details. A larger offset will produce an output less complex with better triangle quality. However, the sharp features (red edges) are well-preserved when the offset parameter is small.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_steiner.jpg)

[Figure 68.7](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_steiner_fig) Steiner points. The projection Steiner points (green) are computed by projecting the triangle circumcenter onto the offset. The intersection Steiner points (blue) are computed as the first intersection point between the Voronoi edge and the offset. (Left) When the offset parameter is small, the algorithm produces more projection Steiner points, which tends to improve the preservation of convex sharp features. (Right) When the offset parameter is large, the algorithm produces more intersection Steiner points, which tends to generate triangles with better quality in terms of angles, in 3D.

By default, we recommend to set the offset parameter to a small fraction of alpha, such that alpha becomes the main parameter that controls the final level of detail.

The image below illustrates the impact of both parameters.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_alpha_offset_bike.jpg)

[Figure 68.8](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_param_grid_fig) Different alpha and offset values on the bike model (533,000 triangles). The x-axis represents the offset value equal to 1/5000, 1/2000, 1/500, 1/200, 1/50, 1/20 and 1/5 of the longest diagonal of the input bounding box, from left to right. The y-axis represents the alpha value equal to 1/300, 1/100, 1/50, 1/20 and 1/5 of the longest diagonal of the input bounding box, from bottom to top. The numbers below each level of detail represents their number of triangles. Depending on the alpha value, an offset too small or too large will produce output mesh with higher complexity. For each alpha, the models with lower complexity can be used as a scale-space representations for collision detection, from near to far distances.

## A Note on "Two-Sided" Wraps

The offset parameter is crucial to our approach because it guarantees that the output is a closed, 2-manifold surface mesh. Indeed, and even when the input is a zero-volume structure such as a single 3D triangle, the output wrap is a thin volume enclosing the said triangle [Figure 68.2](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_input_2_fig).

Users should keep in mind that the wrapping algorithm has no means of determining whether it is acting on the inside or the outside of the unsigned distance field, and will thus produce two-sided wraps in the case of holes in the input and values of alpha smaller than the size of the holes.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_double_sided.jpg)

[Figure 68.9](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_double_sided_fig) Two-sided wrap. (Left) Wrapping a Bunny in 2D, with decreasing values for alpha. (Right) Wrapping a defect-laden Bunny in 3D. The rightmost column depicts a clipped visualization of the inside. When alpha is small enough with respect the diameter of the holes, the algorithm generates a two-sided wrap.

## Performance

The charts below plots the computation times of the wrapping algorithm on the Thingi10k dataset, as well as the complexity of the output triangle mesh.

![](https://doc.cgal.org/latest/Alpha_wrap_3/aw3_thingi10k_benchmark.jpg)

[Figure 68.10](https://doc.cgal.org/latest/Alpha_wrap_3/index.html#fig__aw3_bench_fig) Execution times and output complexity for different values of alpha on the Thingi10k data set. Alpha increases from 1/20 to 1/200 of the length of bounding box diagonal. The x-axis represents the complexity of the output wrap mesh in number of triangle facets. The y-axis represents the total computation time, in seconds. The color and diameter of the dots represent the number of faces in the input triangle soup, ranging from 10 (green) to 3154000 (blue).

## Examples

Here is an example with an input triangle mesh, with alpha set to 1/20 of the bounding box's longest diagonal edge length, and offset set to 1/30 of alpha (i.e., 1/600 of the bounding box diagonal edge length).

**Example:** [Alpha\_wrap\_3/triangle\_mesh\_wrap.cpp](https://doc.cgal.org/latest/Alpha_wrap_3/Alpha_wrap_3_2triangle_mesh_wrap_8cpp-example.html)

Show / Hide

#include "output\_helper.h"

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/alpha\_wrap\_3.h>

#include <CGAL/Polygon\_mesh\_processing/bbox.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Real\_timer.h>

#include \<iostream>

#include \<string>

namespace PMP = CGAL::Polygon\_mesh\_processing;

using K = [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html);

using Point\_3 = K::Point\_3;

using Mesh = CGAL::Surface\_mesh<Point\_3>;

int main(int argc, char\*\* argv)

{

// Read the input

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/armadillo.off");

std::cout << "Reading " << filename << "..." << std::endl;

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh) || [is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172) (mesh) ||![is\_triangle\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga11883d231eec1b58f37efe4acedd9588) (mesh))

{

std::cerr << "Invalid input:" << filename << std::endl;

return EXIT\_FAILURE;

}

std::cout << "Input: " << num\_vertices(mesh) << " vertices, " << num\_faces(mesh) << " faces" << std::endl;

// Compute the alpha and offset values

const double relative\_alpha = (argc > 2)? std::stod(argv\[2\]): 20.;

const double relative\_offset = (argc > 3)? std::stod(argv\[3\]): 600.;

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html) bbox = CGAL::Polygon\_mesh\_processing::bbox(mesh);

const double diag\_length = std::sqrt([CGAL::square](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga07001b5ddc5c43096c811c91a306be9a) (bbox.[xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c) () - bbox.[xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1) ()) +

const double alpha = diag\_length / relative\_alpha;

const double offset = diag\_length / relative\_offset;

std::cout << "alpha: " << alpha << ", offset: " << offset << std::endl;

// Construct the wrap

CGAL::Real\_timer t;

t.start();

Mesh wrap;

[CGAL::alpha\_wrap\_3](https://doc.cgal.org/latest/Alpha_wrap_3/group__AW3__free__functions__grp.html#ga3fcacd2397bd86329faa2855f8475ea5) (mesh, alpha, offset, wrap);

t.stop();

std::cout << "Result: " << num\_vertices(wrap) << " vertices, " << num\_faces(wrap) << " faces" << std::endl;

std::cout << "Took " << t.time() << " s." << std::endl;

// Save the result

const std::string output\_name = generate\_output\_name(filename, relative\_alpha, relative\_offset);

std::cout << "Writing to " << output\_name << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) (output\_name, wrap, CGAL::parameters::stream\_precision(17));

return EXIT\_SUCCESS;

}

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html)

[CGAL::Bbox\_3::ymin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a2088e16a1f0a20e011e5b94c2e9c222a)

double ymin() const

[CGAL::Bbox\_3::xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c)

double xmax() const

[CGAL::Bbox\_3::zmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a6c55430abc7fda54571cf1075c7f2f8b)

double zmin() const

[CGAL::Bbox\_3::zmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a98def8b9515f31ded759d781969ddaf6)

double zmax() const

[CGAL::Bbox\_3::ymax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a9d06f61bd89faa841e011ff53edf745f)

double ymax() const

[CGAL::Bbox\_3::xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1)

double xmin() const

[CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html)

[CGAL::alpha\_wrap\_3](https://doc.cgal.org/latest/Alpha_wrap_3/group__AW3__free__functions__grp.html#ga3fcacd2397bd86329faa2855f8475ea5)

void alpha\_wrap\_3(const PointRange &points, const FaceRange &faces, const double alpha, const double offset, OutputMesh &alpha\_wrap, const InputNamedParameters &in\_np, const OutputNamedParameters &out\_np)

computes a watertight, 2-manifold, and intersection-free triangulated surface mesh that strictly cont...

**Definition:** alpha\_wrap\_3.h:94

[CGAL::square](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga07001b5ddc5c43096c811c91a306be9a)

NT square(const NT &x)

[CGAL::is\_triangle\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga11883d231eec1b58f37efe4acedd9588)

bool is\_triangle\_mesh(const FaceGraph &g)

[CGAL::is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172)

bool is\_empty(const FaceGraph &g)

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66)

bool write\_polygon\_mesh(const std::string &fname, Graph &g, const NamedParameters &np=parameters::default\_values())

Some triangle soups might not be representable as a mesh due to non-manifoldness or incompatible orientations. Such triangle soup is nevertheless a valid input for the wrapping algorithm, as illustrated in the following example.

**Example:** [Alpha\_wrap\_3/triangle\_soup\_wrap.cpp](https://doc.cgal.org/latest/Alpha_wrap_3/Alpha_wrap_3_2triangle_soup_wrap_8cpp-example.html)

Show / Hide

#include "output\_helper.h"

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/alpha\_wrap\_3.h>

#include <CGAL/Polygon\_mesh\_processing/bbox.h>

#include <CGAL/IO/polygon\_soup\_io.h>

#include <CGAL/Real\_timer.h>

#include \<array>

#include \<iostream>

#include \<string>

#include \<vector>

namespace AW3 = CGAL::Alpha\_wraps\_3;

using K = [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html);

using Point\_3 = K::Point\_3;

using Mesh = CGAL::Surface\_mesh<Point\_3>;

int main(int argc, char\*\* argv)

{

std::cout.precision(17);

// Read the input

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby-shuffled.off");

std::cout << "Reading " << filename << "..." << std::endl;

std::vector<Point\_3> points;

std::vector<std::array<std::size\_t, 3> > faces;

if(![CGAL::IO::read\_polygon\_soup](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#gaafb0e02f4669802c727709743065804c) (filename, points, faces) || faces.empty())

{

std::cerr << "Invalid input:" << filename << std::endl;

return EXIT\_FAILURE;

}

std::cout << "Input: " << points.size() << " points, " << faces.size() << " faces" << std::endl;

// Compute the alpha and offset values

const double relative\_alpha = (argc > 2)? std::stod(argv\[2\]): 20.;

const double relative\_offset = (argc > 3)? std::stod(argv\[3\]): 600.;

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html) bbox;

for(const Point\_3& p: points)

bbox += p.bbox();

const double diag\_length = std::sqrt([CGAL::square](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga07001b5ddc5c43096c811c91a306be9a) (bbox.[xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c) () - bbox.[xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1) ()) +

const double alpha = diag\_length / relative\_alpha;

const double offset = diag\_length / relative\_offset;

// Construct the wrap

CGAL::Real\_timer t;

t.start();

Mesh wrap;

[CGAL::alpha\_wrap\_3](https://doc.cgal.org/latest/Alpha_wrap_3/group__AW3__free__functions__grp.html#ga3fcacd2397bd86329faa2855f8475ea5) (points, faces, alpha, offset, wrap);

t.stop();

std::cout << "Result: " << num\_vertices(wrap) << " vertices, " << num\_faces(wrap) << " faces" << std::endl;

std::cout << "Took " << t.time() << " s." << std::endl;

// Save the result

const std::string output\_name = generate\_output\_name(filename, relative\_alpha, relative\_offset);

std::cout << "Writing to " << output\_name << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) (output\_name, wrap, CGAL::parameters::stream\_precision(17));

return EXIT\_SUCCESS;

}

[CGAL::IO::read\_polygon\_soup](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#gaafb0e02f4669802c727709743065804c)

bool read\_polygon\_soup(const std::string &fname, PointRange &points, PolygonRange &polygons, const NamedParameters &np=parameters::default\_values())

Here is an example with a point cloud.

**Example:** [Alpha\_wrap\_3/point\_set\_wrap.cpp](https://doc.cgal.org/latest/Alpha_wrap_3/Alpha_wrap_3_2point_set_wrap_8cpp-example.html)

Show / Hide

#include "output\_helper.h"

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/alpha\_wrap\_3.h>

#include <CGAL/IO/read\_points.h>

#include <CGAL/Real\_timer.h>

#include \<iostream>

#include \<string>

using K = [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html);

using Point\_3 = K::Point\_3;

using Point\_container = std::vector<Point\_3>;

using Mesh = CGAL::Surface\_mesh<Point\_3>;

int main(int argc, char\*\* argv)

{

// Read the input

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("points\_3/oni.pwn");

std::cout << "Reading " << filename << "..." << std::endl;

Point\_container points;

if(![CGAL::IO::read\_points](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#ga8fac388459c5cf96bf11ce3b4e0459c1) (filename, std::back\_inserter(points)) || points.empty())

{

std::cerr << "Invalid input:" << filename << std::endl;

return EXIT\_FAILURE;

}

std::cout << points.size() << " points" << std::endl;

// Compute the alpha and offset values

const double relative\_alpha = (argc > 2)? std::stod(argv\[2\]): 10.;

const double relative\_offset = (argc > 3)? std::stod(argv\[3\]): 300.;

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html) bbox = CGAL::bbox\_3(std::cbegin(points), std::cend(points));

const double diag\_length = std::sqrt([CGAL::square](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga07001b5ddc5c43096c811c91a306be9a) (bbox.[xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c) () - bbox.[xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1) ()) +

const double alpha = diag\_length / relative\_alpha;

const double offset = diag\_length / relative\_offset;

std::cout << "absolute alpha = " << alpha << " absolute offset = " << offset << std::endl;

// Construct the wrap

CGAL::Real\_timer t;

t.start();

Mesh wrap;

[CGAL::alpha\_wrap\_3](https://doc.cgal.org/latest/Alpha_wrap_3/group__AW3__free__functions__grp.html#ga3fcacd2397bd86329faa2855f8475ea5) (points, alpha, offset, wrap);

t.stop();

std::cout << "Result: " << num\_vertices(wrap) << " vertices, " << num\_faces(wrap) << " faces" << std::endl;

std::cout << "Took " << t.time() << " s." << std::endl;

// Save the result

const std::string output\_name = generate\_output\_name(filename, relative\_alpha, relative\_offset);

std::cout << "Writing to " << output\_name << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) (output\_name, wrap, CGAL::parameters::stream\_precision(17));

return EXIT\_SUCCESS;

}

[CGAL::IO::read\_points](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#ga8fac388459c5cf96bf11ce3b4e0459c1)

bool read\_points(const std::string &fname, PointOutputIterator output, const NamedParameters &np=parameters::default\_values())