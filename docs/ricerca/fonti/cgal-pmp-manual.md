CGAL 6.2.1 - Polygon Mesh Processing

Searching...

No Matches

![](https://doc.cgal.org/latest/Polygon_mesh_processing/pmp-banner.png)

Note

With [CGAL](https://doc.cgal.org/latest/BGL/namespaceCGAL.html) 6.2, the "Polygon Mesh Processing" package has been reorganized into several packages. This package retains the core functionalities, while advanced and specialized features have been moved to dedicated packages:  
  
- [Boolean Operations On Meshes](https://doc.cgal.org/latest/Manual/packages.html#PkgPMPBooleanOperations): algorithms for Boolean operations on polygon meshes; clipping, splitting, and slicing with planes, boxes, or other meshes; and kernel computations.
- [Meshing and Remeshing of Polygon Meshes](https://doc.cgal.org/latest/Manual/packages.html#PkgPMPRemeshing): algorithms for meshing and remeshing, such as triangulation, refinement, simplification, optimization, and smoothing.
- [Polygon Mesh Repair](https://doc.cgal.org/latest/Manual/packages.html#PkgPMPMeshRepair): tools for detecting and correcting combinatorial and geometric defects in polygon meshes and polygon soups, including face orientation, hole filling, removal of degeneracies, and boundary stitching.

## Introduction

This package provides a comprehensive set of methods and classes for polygon mesh processing, ranging from basic operations on mesh elements to advanced geometry processing algorithms. The implementation is primarily based on the algorithms and references presented in Botsch et al.'s book on polygon mesh processing [\[2\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_botsch2010PMP).

## Polygon Mesh

A *polygon* *mesh* is a consistent and orientable surface mesh, that can have one or more boundaries. The *faces* are simple polygons. The *edges* are segments. Each edge connects two *vertices*, and is shared by two faces (including the *null* *face* for boundary edges). A polygon mesh can have any number of connected components. In this package, a polygon mesh is considered to have the topology of a 2-manifold. Note that all these requirements are mostly combinatorial, and do not impose any geometric constraints on the shape of the polygons. As such, this definition does not prevent the presence of defects such as self-intersections, degenerate faces or edges, etc.

## API

This package follows the BGL API described in [CGAL and the Boost Graph Library](https://doc.cgal.org/latest/Manual/packages.html#PkgBGL). It can thus be used either with `CGAL::Surface_mesh`, `CGAL::Polyhedron_3`, or any class model of the concept `FaceGraph`. Each function or class of this package details the requirements on the input polygon mesh.

[Named Parameters](https://doc.cgal.org/latest/BGL/index.html#BGLNamedParameters) are used to deal with optional parameters. The page [Named Parameters](https://doc.cgal.org/latest/BGL/group__bgl__namedparameters.html) describes their usage.

## Outline

The algorithms described in this manual are organized in sections:

## Reading and Writing Polygon Meshes

In all functions of this package, the polygon meshes are required to be models of the graph concepts defined in the package [CGAL and the Boost Graph Library](https://doc.cgal.org/latest/Manual/packages.html#PkgBGL). Using common graph concepts enables having common input/output functions for all the models of these concepts. The page [I/O Functions](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html) provides an exhaustive description of the available I/O functions.

In addition, this package offers the function `CGAL::Polygon_mesh_processing::IO::read_polygon_mesh()`, which can perform some repairing if the input data do not represent a manifold surface.

## Predicates

This package provides several predicates to determine the characteristics of a triangle mesh or a subset of its faces.

## Intersections Detection

Intersection tests between triangle meshes and/or polylines can be performed using the function [`CGAL::Polygon_mesh_processing::do_intersect()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__predicates__grp.html) . Additionally, the function `CGAL::Polygon_mesh_processing::intersecting_meshes()` can be used to collect all pairs of intersecting meshes within a range.

### Self-intersections

Self-intersections within a triangle mesh can be detected by calling the function `CGAL::Polygon_mesh_processing::does_self_intersect()`. Additionally, the function `CGAL::Polygon_mesh_processing::self_intersections()` reports all pairs of intersecting triangles.

### Self-intersections Example

The following example demonstrates self-intersection detection in the `pig.off` mesh. Detected self-intersections are illustrated in [Figure 76.2](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__SelfIntersections).

**Example:** [Polygon\_mesh\_processing/self\_intersections\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2self_intersections_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/self\_intersections.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Real\_timer.h>

#include <CGAL/tags.h>

#include \<iostream>

#include \<iterator>

#include \<string>

#include \<vector>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef [CGAL::Surface\_mesh<K::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/pig.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh) ||![CGAL::is\_triangle\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga11883d231eec1b58f37efe4acedd9588) (mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

std::cout << "Using parallel mode? " << std::is\_same<CGAL::Parallel\_if\_available\_tag, CGAL::Parallel\_tag>::value << std::endl;

CGAL::Real\_timer timer;

timer.start();

bool intersecting = PMP::does\_self\_intersect<CGAL::Parallel\_if\_available\_tag>(mesh, CGAL::parameters::vertex\_point\_map(get(CGAL::vertex\_point, mesh)));

std::cout << (intersecting? "There are self-intersections.": "There is no self-intersection.") << std::endl;

std::cout << "Elapsed time (does self intersect): " << timer.time() << std::endl;

timer.reset();

std::vector<std::pair<face\_descriptor, face\_descriptor> > intersected\_tris;

PMP::self\_intersections<CGAL::Parallel\_if\_available\_tag>(faces(mesh), mesh, std::back\_inserter(intersected\_tris));

std::cout << intersected\_tris.size() << " pairs of triangles intersect." << std::endl;

std::cout << "Elapsed time (self intersections): " << timer.time() << std::endl;

return EXIT\_SUCCESS;

}

[CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html)

[CGAL::Surface\_mesh](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html)

[CGAL::is\_triangle\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga11883d231eec1b58f37efe4acedd9588)

bool is\_triangle\_mesh(const FaceGraph &g)

![](https://doc.cgal.org/latest/Polygon_mesh_processing/selfintersections.jpg)

[Figure 76.2](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__SelfIntersections) Detection of self-intersections in a triangle mesh. Intersecting triangles are displayed in dark grey and red in the right image.

## Side of Triangle Mesh

The class `CGAL::Side_of_triangle_mesh` provides a functor that can answer whether a query point is inside, outside, or on the boundary of the domain bounded by a given closed triangle mesh.

A point is considered to be on the bounded side of the mesh if an odd number of surfaces are crossed when moving from the point to infinity.

The algorithm can handle the case of a triangle mesh with several connected components, but is expected to contain no self-intersections. In case of self-inclusions, the ray intersections parity test is performed, and the execution will not fail. However, users should be aware that the predicate alternately considers sub-volumes to be on the bounded and unbounded sides of the input triangle mesh.

**Example:** [Polygon\_mesh\_processing/point\_inside\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2point_inside_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedron\_3.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/point\_generators\_3.h>

#include <CGAL/Side\_of\_triangle\_mesh.h>

#include \<iostream>

#include \<limits>

#include \<string>

#include \<vector>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef K::Point\_3 Point;

typedef [CGAL::Polyhedron\_3\<K>](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html) Mesh;

namespace PMP = CGAL::Polygon\_mesh\_processing;

double max\_coordinate(const Mesh& poly)

{

double max\_coord = -std::numeric\_limits\<double>::infinity();

for(Mesh::Vertex\_handle v: vertices(poly))

{

Point p = v->point();

max\_coord = (std::max)(max\_coord, [CGAL::to\_double](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga1f1bcd74fce34fd532445590bbda5cd5) (p.x()));

max\_coord = (std::max)(max\_coord, [CGAL::to\_double](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga1f1bcd74fce34fd532445590bbda5cd5) (p.y()));

max\_coord = (std::max)(max\_coord, [CGAL::to\_double](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga1f1bcd74fce34fd532445590bbda5cd5) (p.z()));

}

return max\_coord;

}

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/eight.off");

Mesh poly;

if(!PMP::IO::read\_polygon\_mesh(filename, poly) || [CGAL::is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172) (poly) ||![CGAL::is\_triangle\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga11883d231eec1b58f37efe4acedd9588) (poly))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

[CGAL::Side\_of\_triangle\_mesh<Mesh, K>](https://doc.cgal.org/latest/Polygon_mesh_processing/classCGAL_1_1Side__of__triangle__mesh.html) inside(poly);

double size = max\_coordinate(poly);

unsigned int nb\_points = 100;

std::vector\<Point> points;

points.reserve(nb\_points);

[CGAL::Random\_points\_in\_cube\_3\<Point>](https://doc.cgal.org/latest/Generator/classCGAL_1_1Random__points__in__cube__3.html) gen(size);

for (unsigned int i = 0; i < nb\_points; ++i)

points.push\_back(\*gen++);

std::cout << "Test " << nb\_points << " random points in cube "

<< "\[-" << size << "; " << size <<"\]" << std::endl;

int nb\_inside = 0;

int nb\_boundary = 0;

for (std::size\_t i = 0; i < nb\_points; ++i)

{

[CGAL::Bounded\_side](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gaf6030e89dadcc1f45369b0cdc5d9e111) res = inside(points\[i\]);

if (res == [CGAL::ON\_BOUNDED\_SIDE](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ggaf6030e89dadcc1f45369b0cdc5d9e111ad8333d35d4801c08b3a5ae9e94d7cabe)) { ++nb\_inside; }

if (res == [CGAL::ON\_BOUNDARY](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ggaf6030e89dadcc1f45369b0cdc5d9e111a060193157c0875fb2e6445a648f3ac1f)) { ++nb\_boundary; }

}

std::cerr << "Total query size: " << points.size() << std::endl;

std::cerr << " " << nb\_inside << " points inside " << std::endl;

std::cerr << " " << nb\_boundary << " points on boundary " << std::endl;

std::cerr << " " << points.size() - nb\_inside - nb\_boundary << " points outside " << std::endl;

return 0;

}

[CGAL::Polyhedron\_3](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html)

[CGAL::Random\_points\_in\_cube\_3](https://doc.cgal.org/latest/Generator/classCGAL_1_1Random__points__in__cube__3.html)

[CGAL::Side\_of\_triangle\_mesh](https://doc.cgal.org/latest/Polygon_mesh_processing/classCGAL_1_1Side__of__triangle__mesh.html)

This class provides an efficient point location functionality with respect to a domain bounded by one...

**Definition:** Side\_of\_triangle\_mesh.h:77

[CGAL::to\_double](https://doc.cgal.org/latest/Algebraic_foundations/group__PkgAlgebraicFoundationsRef.html#ga1f1bcd74fce34fd532445590bbda5cd5)

double to\_double(const NT &x)

[CGAL::is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172)

bool is\_empty(const FaceGraph &g)

[CGAL::Bounded\_side](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gaf6030e89dadcc1f45369b0cdc5d9e111)

Bounded\_side

[CGAL::ON\_BOUNDARY](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ggaf6030e89dadcc1f45369b0cdc5d9e111a060193157c0875fb2e6445a648f3ac1f)

ON\_BOUNDARY

[CGAL::ON\_BOUNDED\_SIDE](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ggaf6030e89dadcc1f45369b0cdc5d9e111ad8333d35d4801c08b3a5ae9e94d7cabe)

ON\_BOUNDED\_SIDE

## Polyhedral Envelope Containment Check

The class `CGAL::Polyhedral_envelope` provides functors to check whether a query point, segment, or triangle is fully contained within a *polyhedral envelope* of a triangle mesh or triangle soup.

A polyhedral envelope is a conservative approximation of the Minkowski sum envelope of a set of triangles with a sphere of radius $\epsilon$. The Minkowski sum envelope features cylindrical and spherical patches at convex edges and vertices.

Given a distance $\delta =  \epsilon / \sqrt(3)$, a *prism* is associated with each triangle by intersecting halfspaces parallel and orthogonal to the triangle and its edges, and additional halfspaces for obtuse angles, with face normals corresponding to angle bisectors. These halfspaces are at distance $\delta$ and contain the triangle.

The *polyhedral envelope* of a set of triangles with a tolerance $\epsilon$ then is the union of the prisms of all faces with $\delta = \epsilon / \sqrt(3)$.

![](https://doc.cgal.org/latest/Polygon_mesh_processing/envelope.png)

[Figure 76.3](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__envelopeFig) The prism for a single triangle (left), the polyhedral envelope (middle), and the Minkowski sum envelope (right) for a triangle mesh.

The polyhedral envelope is guaranteed to be contained within the Minkowski sum envelope. The containment test is exact for the polyhedral envelope and conservative for the Minkowski sum envelope: if a query is inside the polyhedral envelope, it is also inside the Minkowski sum envelope; if outside, its relation to the Minkowski sum envelope is undetermined.

The algorithm of Wang et al. [\[8\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:Wwshap-eepec-20) for polyhedral envelope containment proceeds as follows:

The prisms of the faces of the input triangles are stored in an AABB tree, which is used to quickly identify the prisms whose bounding box overlaps with the query.

For a query point, the algorithm checks if it is inside one of these prisms. For a query segment or triangle, the algorithm checks if the query is completely covered. The details of how to check this covering can be found in the paper.

Polyhedral envelope containment is used by `Surface_mesh_simplification::Polyhedral_envelope_filter` in the [Triangulated Surface Mesh Simplification](https://doc.cgal.org/latest/Manual/packages.html#PkgSurfaceMeshSimplification) package to simplify triangle meshes within a given tolerance.

### Polyhedral Envelope Examples

The following example demonstrates construction of a polyhedral envelope for a `CGAL::Surface_mesh` and performing queries.

**Example:** [Polygon\_mesh\_processing/polyhedral\_envelope.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2polyhedral_envelope_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedral\_envelope.h>

#include <CGAL/Surface\_mesh.h>

#include \<iostream>

#include \<fstream>

int main(int argc, char\* argv\[\])

{

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point\_3;

typedef [CGAL::Surface\_mesh<Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef [CGAL::Polyhedral\_envelope\<Kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polyhedral__envelope.html) Envelope;

std::ifstream in((argc>1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby.off"));

Mesh tmesh;

in >> tmesh;

double eps = (argc>2)? std::stod(std::string(argv\[2\])): 0.2;

Envelope envelope(tmesh, eps);

int i = (argc>3)? std::stoi(std::string(argv\[3\])): 0;

int j = (argc>4)? std::stoi(std::string(argv\[4\])): 100;

int k = (argc>5)? std::stoi(std::string(argv\[5\])): 200;

if(envelope(tmesh.point(vertex\_descriptor(i)),

tmesh.point(vertex\_descriptor(j)),

tmesh.point(vertex\_descriptor(k)))){

std::cout << "inside polyhedral envelope" << std::endl;

}

return 0;

}

[Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html)

[Kernel](https://doc.cgal.org/latest/Kernel_23/namespaceKernel.html)

[CGAL::Polyhedral\_envelope](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polyhedral__envelope.html)

This class can be used to check if a query point, segment, or triangle is inside or outside a polyhed...

**Definition:** Polyhedral\_envelope.h:105

As connectivity information is not required, the same check can be performed on a triangle soup.

**Example:** [Polygon\_mesh\_processing/polyhedral\_envelope\_of\_triangle\_soup.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2polyhedral_envelope_of_triangle_soup_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedral\_envelope.h>

#include <CGAL/IO/OFF.h>

#include \<iostream>

#include \<fstream>

#include \<vector>

int main(int argc, char\* argv\[\])

{

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point\_3;

typedef [CGAL::Polyhedral\_envelope\<Kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polyhedral__envelope.html) Envelope;

std::ifstream in((argc>1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby.off"));

double eps = (argc>2)? std::stod(std::string(argv\[2\])): 0.2;

std::vector<Point\_3> points;

std::vector<std::vector<std::size\_t> > polygons;

[CGAL::IO::read\_OFF](https://doc.cgal.org/latest/BGL/group__PkgBGLIoFuncsOFF.html#gadd0f59b6789ef565bb7e95f3d0d89e91) (in, points, polygons);

Envelope envelope(points, polygons, eps);

int i = (argc>3)? std::stoi(std::string(argv\[3\])): 0;

int j = (argc>4)? std::stoi(std::string(argv\[4\])): 100;

int k = (argc>5)? std::stoi(std::string(argv\[5\])): 200;

if (envelope(points\[i\], points\[j\],points\[k\]))

{

std::cout << "inside polyhedral envelope" << std::endl;

}

return 0;

}

[CGAL::IO::read\_OFF](https://doc.cgal.org/latest/BGL/group__PkgBGLIoFuncsOFF.html#gadd0f59b6789ef565bb7e95f3d0d89e91)

bool read\_OFF(std::istream &is, Graph &g, const NamedParameters &np=parameters::default\_values())

A triangle mesh can also be used as a query to verify if a remeshed version is contained within the polyhedral envelope of an input mesh.

**Example:** [Polygon\_mesh\_processing/polyhedral\_envelope\_mesh\_containment.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2polyhedral_envelope_mesh_containment_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedral\_envelope.h>

#include <CGAL/Polygon\_mesh\_processing/remesh.h>

#include <CGAL/Surface\_mesh.h>

#include \<algorithm>

#include \<iostream>

#include \<fstream>

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point\_3;

typedef [CGAL::Surface\_mesh<Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef [CGAL::Polyhedral\_envelope\<Kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polyhedral__envelope.html) Envelope;

std::ifstream in((argc>1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby.off"));

Mesh tmesh;

in >> tmesh;

// remesh the input using the longest edge size as target edge length

Mesh query = tmesh;

Mesh::Edge\_iterator longest\_edge\_it =

std::max\_element(edges(query).begin(), edges(query).end(),

\[&query\](Mesh::Edge\_index e1, Mesh::Edge\_index e2)

{

return [PMP::edge\_length](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__measure__grp.html#gaaffc67e631d83a7da4b1096b782ead94) (halfedge(e1, query), query) <

[PMP::edge\_length](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__measure__grp.html#gaaffc67e631d83a7da4b1096b782ead94) (halfedge(e2, query), query);

});

[PMP::isotropic\_remeshing](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__local__remeshing__grp.html#ga412f696ec3009074bf957f1bba638248) (faces(tmesh), [PMP::edge\_length](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__measure__grp.html#gaaffc67e631d83a7da4b1096b782ead94) (halfedge(\*longest\_edge\_it, query), query), query);

// construct the polyhedral envelope

const double eps = (argc>2)? std::stod(std::string(argv\[2\])): 0.01;

Envelope envelope(tmesh, eps);

// check is the remeshed version is inside the polyhedral envelope of the input mesh

if ( envelope(query) )

std::cout << "Remeshing is inside the polyhedral envelope\\n";

else

std::cout << "Remeshing is not inside the polyhedral envelope\\n";

std::ofstream("remeshed.off") << query;

return 0;

}

[CGAL::Polygon\_mesh\_processing::isotropic\_remeshing](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__local__remeshing__grp.html#ga412f696ec3009074bf957f1bba638248)

void isotropic\_remeshing(const FaceRange &faces, SizingFunction &sizing, PolygonMesh &pmesh, const NamedParameters &np=parameters::default\_values())

[CGAL::Polygon\_mesh\_processing::edge\_length](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__measure__grp.html#gaaffc67e631d83a7da4b1096b782ead94)

FT edge\_length(typename boost::graph\_traits< PolygonMesh >::halfedge\_descriptor h, const PolygonMesh &pmesh, const NamedParameters &np=parameters::default\_values())

computes the length of an edge of a given polygon mesh.

**Definition:** measure.h:109

## Shape Predicates

Badly shaped or, even worse, completely degenerate elements of a polygon mesh are problematic in many algorithms which one might want to use on the mesh. This package offers a toolkit of functions to detect such undesirable elements.

- `CGAL::Polygon_mesh_processing::is_degenerate_edge()`, to detect if an edge is degenerate (that is, if its two vertices share the same geometric location).
- `CGAL::Polygon_mesh_processing::is_degenerate_triangle_face()`, to detect if a face is degenerate (that is, if its three vertices are collinear).
- `CGAL::Polygon_mesh_processing::degenerate_edges()`, to collect degenerate edges within a range of edges.
- `CGAL::Polygon_mesh_processing::degenerate_faces()`, to collect degenerate faces within a range of faces.
- `CGAL::Polygon_mesh_processing::is_cap_triangle_face()`, to detect if a face has one very large angle.
- `CGAL::Polygon_mesh_processing::is_needle_triangle_face()`, to detect if a face has a very short edge.

## Connected Components

## Collecting Connected Components

Functions are provided to enumerate and store the connected components of a polygon mesh. Connected components may be closed and geometrically separated, or separated by border or user-specified *constraint* edges.

The main entry point is the function `CGAL::Polygon_mesh_processing::connected_components()`, which collects all the connected components and fills a property map with the indices of the different connected components.

If a single connected component is to be extracted, the function `CGAL::Polygon_mesh_processing::connected_component()` collects all the faces that belong to the same connected component as the face that is provided as a parameter.

When a mesh has no boundary, it partitions the 3D space in different volumes. The function `CGAL::Polygon_mesh_processing::volume_connected_components()` can be used to assign to each face an id per volume defined by the surface connected components.

## Modifying Connected Components

It is often useful to retain or remove specific connected components, for example, to discard small noisy components in favor of larger ones.

The functions `CGAL::Polygon_mesh_processing::keep_connected_components()` and `CGAL::Polygon_mesh_processing::remove_connected_components()` enable the user to keep or remove only a selection of connected components, provided either as a range of faces that belong to the desired connected components or as a range of connected component ids (one or more per connected component).

Finally, it can be useful to quickly remove some connected components based on characteristics of the surface mesh. The function `CGAL::Polygon_mesh_processing::keep_largest_connected_components()` enables the user to keep only a given number from the largest connected components. The size of a connected component is given by the sum of the sizes of the faces it contains; by default, the size of a face is `1`, and thus the size of a connected component is equal to the number of faces it contains. However, it is also possible to pass a face size map, such that the size of the face is its area, for example. Similarly to the previous function, the function `CGAL::Polygon_mesh_processing::keep_large_connected_components()` can be used to discard all connected components whose size is below a user-defined threshold.

Finally, `CGAL::Polygon_mesh_processing::split_connected_components()` splits the mesh into separate meshes for each connected component.

## Connected Components Examples

The first example shows how to record the connected components of a polygon mesh. In particular, we provide an example for the optional parameter `EdgeConstraintMap`, a property map that returns information about an edge being a *constraint* or not. A *constraint* provides a means to demarcate the border of a connected component, and prevents the propagation of a connected component index to cross it.

**Example:** [Polygon\_mesh\_processing/connected\_components\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2connected_components_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/connected\_components.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <boost/iterator/function\_output\_iterator.hpp>

#include <boost/property\_map/property\_map.hpp>

#include \<iostream>

#include \<iterator>

#include \<map>

#include \<string>

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point;

typedef Kernel::Compare\_dihedral\_angle\_3 Compare\_dihedral\_angle\_3;

typedef [CGAL::Surface\_mesh\<Point>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

namespace PMP = CGAL::Polygon\_mesh\_processing;

template \<typename G>

struct Constraint

{

typedef typename boost::graph\_traits\<G>::edge\_descriptor edge\_descriptor;

typedef boost::readable\_property\_map\_tag category;

typedef bool value\_type;

typedef bool reference;

typedef edge\_descriptor key\_type;

Constraint()

:g\_(NULL)

{}

Constraint(G& g, double bound)

: g\_(&g), bound\_(bound)

{}

value\_type operator\[\](edge\_descriptor e) const

{

const G& g = \*g\_;

return compare\_(g.point(source(e, g)),

g.point(target(e, g)),

g.point(target(next(halfedge(e, g), g), g)),

g.point(target(next([opposite](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gad0a8110cb95f76bac65649bfe58c650b) (halfedge(e, g), g), g), g)),

bound\_) == [CGAL::SMALLER](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gga84351c7e66be00efccd4ab1a61070469ab925c6b1ff8cd0bdea7f31fe18d3c38b);

}

friend inline

value\_type get(const Constraint& m, const key\_type k)

{

return m\[k\];

}

const G\* g\_;

Compare\_dihedral\_angle\_3 compare\_;

double bound\_;

};

template \<typename PM>

struct Put\_true

{

Put\_true(const PM pm)

:pm(pm)

{}

template \<typename T>

void operator()(const T& t)

{

put(pm, t, true);

}

PM pm;

};

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby\_3cc.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

const double bound = std::cos(0.75 \* CGAL\_PI);

std::vector<face\_descriptor> cc;

face\_descriptor fd = \*faces(mesh).first;

[PMP::connected\_component](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gad417b04f530806789515a25530547a36) (fd,

mesh,

std::back\_inserter(cc));

std::cerr << "Connected components without edge constraints" << std::endl;

std::cerr << cc.size() << " faces in the CC of " << fd << std::endl;

// Instead of writing the faces into a container, you can set a face property to true

typedef Mesh::Property\_map<face\_descriptor, bool> F\_select\_map;

F\_select\_map fselect\_map =

mesh.add\_property\_map<face\_descriptor, bool>("f:select", false).first;

[PMP::connected\_component](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gad417b04f530806789515a25530547a36) (fd,

mesh,

boost::make\_function\_output\_iterator(Put\_true<F\_select\_map>(fselect\_map)));

std::cerr << "\\nConnected components with edge constraints (dihedral angle < 3/4 pi)" << std::endl;

Mesh::Property\_map<face\_descriptor, std::size\_t> fccmap =

mesh.add\_property\_map<face\_descriptor, std::size\_t>("f:CC").first;

std::size\_t num = [PMP::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9) (mesh,

fccmap,

CGAL::parameters::edge\_is\_constrained\_map(Constraint\<Mesh>(mesh, bound)));

std::cerr << "- The graph has " << num << " connected components (face connectivity)" << std::endl;

typedef std::map<std::size\_t/\*index of CC\*/, unsigned int/\*nb\*/> Components\_size;

Components\_size nb\_per\_cc;

for(face\_descriptor f: faces(mesh)){

nb\_per\_cc\[ fccmap\[f\] \]++;

}

for(const Components\_size::value\_type& cc: nb\_per\_cc){

std::cout << "\\t CC #" << cc.first

<< " is made of " << cc.second << " faces" << std::endl;

}

std::cerr << "- We keep only components which have at least 4 faces" << std::endl;

[PMP::keep\_large\_connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gad08d3489808a6ec8382a9fba3d288f39) (mesh,

4,

CGAL::parameters::edge\_is\_constrained\_map(Constraint\<Mesh>(mesh, bound)));

std::cerr << "- We keep the two largest components" << std::endl;

[PMP::keep\_largest\_connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gae3812da28af74bdf9602a70ae1f9c817) (mesh,

2,

CGAL::parameters::edge\_is\_constrained\_map(Constraint\<Mesh>(mesh, bound)));

return 0;

}

[CGAL::Polygon\_mesh\_processing::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9)

boost::property\_traits< FaceComponentMap >::value\_type connected\_components(const PolygonMesh &pmesh, FaceComponentMap fcm, const NamedParameters &np=parameters::default\_values())

computes for each face the index of the corresponding connected component.

**Definition:** connected\_components.h:199

[CGAL::Polygon\_mesh\_processing::keep\_large\_connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gad08d3489808a6ec8382a9fba3d288f39)

std::size\_t keep\_large\_connected\_components(PolygonMesh &pmesh, const ThresholdValueType threshold\_value, const NamedParameters &np=parameters::default\_values())

removes connected components whose size is (strictly) smaller than a given threshold value,...

**Definition:** connected\_components.h:537

[CGAL::Polygon\_mesh\_processing::connected\_component](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gad417b04f530806789515a25530547a36)

FaceOutputIterator connected\_component(typename boost::graph\_traits< PolygonMesh >::face\_descriptor seed\_face, const PolygonMesh &pmesh, FaceOutputIterator out, const NamedParameters &np=parameters::default\_values())

discovers all the faces in the same connected component as seed\_face and records them in out.

**Definition:** connected\_components.h:119

[CGAL::Polygon\_mesh\_processing::keep\_largest\_connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#gae3812da28af74bdf9602a70ae1f9c817)

std::size\_t keep\_largest\_connected\_components(PolygonMesh &pmesh, std::size\_t nb\_components\_to\_keep, const NamedParameters &np=parameters::default\_values())

removes all but a user-defined number of connected components.

**Definition:** connected\_components.h:386

[CGAL::opposite](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gad0a8110cb95f76bac65649bfe58c650b)

Oriented\_side opposite(const Oriented\_side &o)

[CGAL::SMALLER](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#gga84351c7e66be00efccd4ab1a61070469ab925c6b1ff8cd0bdea7f31fe18d3c38b)

SMALLER

The second example shows how to use the class template `Face_filtered_graph`, which enables treating one or several connected components as a separate face graph.

**Example:** [Polygon\_mesh\_processing/face\_filtered\_graph\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2face_filtered_graph_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/connected\_components.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/boost/graph/Face\_filtered\_graph.h>

#include <boost/property\_map/property\_map.hpp>

#include \<iostream>

#include \<map>

#include \<string>

#include \<vector>

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point;

typedef [CGAL::Surface\_mesh\<Point>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

typedef boost::graph\_traits\<Mesh>::faces\_size\_type faces\_size\_type;

typedef Mesh::Property\_map<face\_descriptor, faces\_size\_type> FCCmap;

typedef [CGAL::Face\_filtered\_graph\<Mesh>](https://doc.cgal.org/latest/BGL/structCGAL_1_1Face__filtered__graph.html) Filtered\_graph;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby\_3cc.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

FCCmap fccmap = mesh.add\_property\_map<face\_descriptor, faces\_size\_type>("f:CC").first;

faces\_size\_type num = [PMP::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9) (mesh,fccmap);

std::cerr << "- The graph has " << num << " connected components (face connectivity)" << std::endl;

std::cout << "The faces in component 0 are:" << std::endl;

Filtered\_graph ffg(mesh, 0, fccmap);

for(boost::graph\_traits<Filtered\_graph>::face\_descriptor f: faces(ffg))

std::cout << f << std::endl;

if(num > 1)

{

std::vector<faces\_size\_type> components;

components.push\_back(0);

components.push\_back(1);

std::cout << "The faces in components 0 and 1 are:" << std::endl;

ffg.set\_selected\_faces(components, fccmap);

for(Filtered\_graph::face\_descriptor f: faces(ffg))

std::cout << f << std::endl;

}

return 0;

}

[CGAL::Face\_filtered\_graph](https://doc.cgal.org/latest/BGL/structCGAL_1_1Face__filtered__graph.html)

## Surface Location Functions

To ease the manipulation of points on a surface, CGAL offers a multitude of functions based upon a different representation of a point on a polygon mesh: the point is represented as a pair of a face of the polygon mesh and a triplet of barycentric coordinates. This definition enables a robust handling of polylines between points living in the same face: for example, two 3D segments created by four points within the same face that should intersect might not actually intersect due to inexact computations. However, manipulating these same points through their barycentric coordinates can instead be done, and intersections computed in the barycentric space will not suffer from the same issues. Furthermore, this definition is only dependent on the intrinsic dimension of the surface (i.e. 2) and not on the ambient dimension within which the surface is embedded.

The functions of the group [Location Functions](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html) offer the following functionalities:

- location computations: `CGAL::Polygon_mesh_processing::locate()` and similar,
- finding the nearest point on a mesh given a point or a ray: `CGAL::Polygon_mesh_processing::locate_with_AABB_tree()` and similar,
- location-based predicates: `CGAL::Polygon_mesh_processing::is_on_face_border()` and similar.

## Surface Location Example

The following example demonstrates usage of these functions.

**Example:** [Polygon\_mesh\_processing/locate\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2locate_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/locate.h>

#include <CGAL/Polygon\_mesh\_processing/triangulate\_faces.h>

#include <CGAL/AABB\_face\_graph\_triangle\_primitive.h>

#include <CGAL/AABB\_tree.h>

#include <CGAL/AABB\_traits\_3.h>

#include <CGAL/boost/graph/helpers.h>

#include <CGAL/Dynamic\_property\_map.h>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef K::FT FT;

typedef K::Point\_2 Point\_2;

typedef K::Ray\_2 Ray\_2;

typedef K::Point\_3 Point\_3;

typedef K::Ray\_3 Ray\_3;

typedef [CGAL::Surface\_mesh<Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef typename boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef typename boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace CP = [CGAL::parameters](https://doc.cgal.org/latest/STL_Extension/namespaceCGAL_1_1parameters.html);

namespace PMP = CGAL::Polygon\_mesh\_processing;

typedef [PMP::Barycentric\_coordinates\<FT>](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga6581d3f34a14d533fdab2e6beef2873f) Barycentric\_coordinates;

typedef [PMP::Face\_location<Mesh, FT>](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga35604eae6b378b8254a3f41f1a274b9e) Face\_location;

int main(int /\*argc\*/, char\*\* /\*argv\*/)

{

// Generate a simple 3D triangle mesh that with vertices on the plane xOy

Mesh tm;

[CGAL::make\_grid](https://doc.cgal.org/latest/BGL/group__PkgBGLGeneratorFct.html#ga021bca7693efee1d05492ee52583793a) (10, 10, tm);

[PMP::triangulate\_faces](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__meshing__grp.html#ga5e4f69483f6506429c4743de745e7b09) (tm);

// Basic usage

Face\_location random\_location = PMP::random\_location\_on\_mesh\<FT>(tm);

const face\_descriptor f = random\_location.first;

const Barycentric\_coordinates& coordinates = random\_location.second;

std::cout << "Random location on the mesh: face " << f

<< " and with coordinates \[" << coordinates\[0\] << "; "

<< coordinates\[1\] << "; "

<< coordinates\[2\] << "\]\\n";

std::cout << "It corresponds to point (" << [PMP::construct\_point](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga7632ebc56378e6ded961eab21540cecb) (random\_location, tm) << ")\\n\\n";

// Locate a known 3D point in the mesh

const Point\_3 query(1.2, 7.4, 0);

Face\_location query\_location = [PMP::locate](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga817d3417a9711b3efbfde45e46e0aa00) (query, tm);

std::cout << "Point (" << query << ") is located in face " << query\_location.first

<< " with barycentric coordinates \[" << query\_location.second\[0\] << "; "

<< query\_location.second\[1\] << "; "

<< query\_location.second\[2\] << "\]\\n\\n";

// Locate a 3D point in the mesh as the intersection of the mesh and a 3D ray.

// The AABB tree can be cached in case many queries are performed (otherwise, it is rebuilt

// on each call, which is expensive).

typedef [CGAL::AABB\_face\_graph\_triangle\_primitive\<Mesh>](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__face__graph__triangle__primitive.html) AABB\_face\_graph\_primitive;

typedef [CGAL::AABB\_traits\_3<K, AABB\_face\_graph\_primitive>](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__traits__3.html) AABB\_face\_graph\_traits;

[CGAL::AABB\_tree<AABB\_face\_graph\_traits>](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__tree.html) tree;

[PMP::build\_AABB\_tree](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#gafa64630e9a7b1cbc28875d63ac8a3eaa) (tm, tree);

const Ray\_3 ray\_3(Point\_3(4.2, 6.8, 2.4), Point\_3(7.2, 2.3, -5.8));

Face\_location ray\_location = [PMP::locate\_with\_AABB\_tree](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga609d1fd3a16ecc381a1b131386fc708c) (ray\_3, tree, tm);

std::cout << "Intersection of the 3D ray and the mesh is in face " << ray\_location.first

<< " with barycentric coordinates \[" << ray\_location.second\[0\] << " "

<< ray\_location.second\[1\] << " "

<< ray\_location.second\[2\] << "\]\\n";

std::cout << "It corresponds to point (" << [PMP::construct\_point](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga7632ebc56378e6ded961eab21540cecb) (ray\_location, tm) << ")\\n";

std::cout << "Is it on the face's border? " << ([PMP::is\_on\_face\_border](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga455a6b4f1edfd88358a1150c870691e9) (ray\_location, tm)? "Yes": "No") << "\\n\\n";

// -----------------------------------------------------------------------------------------------

// Now, we artificially project the mesh to the natural 2D dimensional plane, with a little translation

// via a custom vertex point property map

typedef [CGAL::dynamic\_vertex\_property\_t<Point\_2>](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__vertex__property__t.html) Point\_2\_property;

typedef typename boost::property\_map<Mesh, Point\_2\_property>::type Projection\_pmap;

Projection\_pmap projection\_pmap = get(Point\_2\_property(), tm);

for(vertex\_descriptor v: vertices(tm))

{

const Point\_3& p = tm.point(v);

put(projection\_pmap, v, Point\_2(p.x() + 1, p.y())); // simply ignoring the z==0 coordinate and translating along Ox

}

// Locate the same 3D point but in a 2D context

const Point\_2 query\_2(query.x() + 1, query.y());

Face\_location query\_location\_2 = [PMP::locate](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga817d3417a9711b3efbfde45e46e0aa00) (query\_2, tm, CP::vertex\_point\_map(projection\_pmap));

std::cout << "Point (" << query\_2 << ") is located in face " << query\_location\_2.first

<< " with barycentric coordinates \[" << query\_location\_2.second\[0\] << "; "

<< query\_location\_2.second\[1\] << "; "

<< query\_location\_2.second\[2\] << "\]\\n\\n";

// Shoot a 2D ray and locate the intersection with the mesh in 2D

const Ray\_2 ray\_2(Point\_2(-10, -10), Point\_2(10, 10));

Face\_location ray\_location\_2 = [PMP::locate](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga817d3417a9711b3efbfde45e46e0aa00) (ray\_2, tm, CP::vertex\_point\_map(projection\_pmap)); // This rebuilds an AABB tree on each call

std::cout << "Intersection of the 2D ray and the mesh is in face " << ray\_location\_2.first

<< " with barycentric coordinates \[" << ray\_location\_2.second\[0\] << "; "

<< ray\_location\_2.second\[1\] << "; "

<< ray\_location\_2.second\[2\] << "\]\\n";

std::cout << "It corresponds to point (" << [PMP::construct\_point](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga7632ebc56378e6ded961eab21540cecb) (ray\_location\_2, tm, CP::vertex\_point\_map(projection\_pmap)) << ")\\n";

if([PMP::is\_on\_mesh\_border](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga905f903215a1123afef50b74d5424bda) (ray\_location\_2, tm))

std::cout << "It is on the border of the mesh!\\n" << std::endl;

return EXIT\_SUCCESS;

}

[CGAL::AABB\_face\_graph\_triangle\_primitive](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__face__graph__triangle__primitive.html)

[CGAL::AABB\_traits\_3](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__traits__3.html)

[CGAL::AABB\_tree](https://doc.cgal.org/latest/AABB_tree/classCGAL_1_1AABB__tree.html)

[CGAL::Polygon\_mesh\_processing::Face\_location](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga35604eae6b378b8254a3f41f1a274b9e)

std::pair< typename boost::graph\_traits< TriangleMesh >::face\_descriptor, Barycentric\_coordinates< FT > > Face\_location

If tm is the input triangulated surface mesh and given the pair (f, bc) such that bc is the triplet o...

**Definition:** locate.h:83

[CGAL::Polygon\_mesh\_processing::is\_on\_face\_border](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga455a6b4f1edfd88358a1150c870691e9)

bool is\_on\_face\_border(const Face\_location< TriangleMesh, FT > &loc, const TriangleMesh &tm)

Given a location, returns whether the location is on the boundary of the face or not.

**Definition:** locate.h:790

[CGAL::Polygon\_mesh\_processing::locate\_with\_AABB\_tree](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga609d1fd3a16ecc381a1b131386fc708c)

Face\_location< TriangleMesh, FT > locate\_with\_AABB\_tree(const Point &p, const AABB\_tree< AABB\_traits\_3< Geom\_traits, AABB\_face\_graph\_triangle\_primitive< TriangleMesh, Point3VPM > > > &tree, const TriangleMesh &tm, const NamedParameters &np=parameters::default\_values())

returns the face location nearest to the given point, as a location.

**Definition:** locate.h:1599

[CGAL::Polygon\_mesh\_processing::Barycentric\_coordinates](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga6581d3f34a14d533fdab2e6beef2873f)

std::array< FT, 3 > Barycentric\_coordinates

A triplet of coordinates describing the barycentric coordinates of a point with respect to the vertic...

**Definition:** locate.h:71

[CGAL::Polygon\_mesh\_processing::construct\_point](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga7632ebc56378e6ded961eab21540cecb)

Point construct\_point(const Face\_location< TriangleMesh, FT > &loc, const TriangleMesh &tm, const NamedParameters &np=parameters::default\_values())

Given a location in a face, returns the geometric position described by these coordinates,...

**Definition:** locate.h:591

[CGAL::Polygon\_mesh\_processing::locate](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga817d3417a9711b3efbfde45e46e0aa00)

Face\_location< TriangleMesh, FT > locate(const Point &p, const TriangleMesh &tm, const NamedParameters &np=parameters::default\_values())

returns the nearest face location to the given point.

**Definition:** locate.h:1688

[CGAL::Polygon\_mesh\_processing::is\_on\_mesh\_border](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#ga905f903215a1123afef50b74d5424bda)

bool is\_on\_mesh\_border(const Face\_location< TriangleMesh, FT > &loc, const TriangleMesh &tm)

Given a location, returns whether the location is on the border of the mesh or not.

**Definition:** locate.h:826

[CGAL::Polygon\_mesh\_processing::build\_AABB\_tree](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__locate__grp.html#gafa64630e9a7b1cbc28875d63ac8a3eaa)

void build\_AABB\_tree(const TriangleMesh &tm, AABB\_tree< AABB\_traits\_3< Geom\_traits, CGAL::AABB\_face\_graph\_triangle\_primitive< TriangleMesh, Point3VPM > > > &outTree, const NamedParameters &np=parameters::default\_values())

creates an AABB tree suitable for use with locate\_with\_AABB\_tree().

**Definition:** locate.h:1524

[CGAL::Polygon\_mesh\_processing::triangulate\_faces](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__meshing__grp.html#ga5e4f69483f6506429c4743de745e7b09)

bool triangulate\_faces(const FaceRange &face\_range, PolygonMesh &pmesh, const NamedParameters &np=parameters::default\_values())

[CGAL::make\_grid](https://doc.cgal.org/latest/BGL/group__PkgBGLGeneratorFct.html#ga021bca7693efee1d05492ee52583793a)

boost::graph\_traits< Graph >::halfedge\_descriptor make\_grid(typename boost::graph\_traits< Graph >::vertices\_size\_type i, typename boost::graph\_traits< Graph >::vertices\_size\_type j, Graph &g, const CoordinateFunctor &calculator, bool triangulated=false)

[CGAL::parameters](https://doc.cgal.org/latest/STL_Extension/namespaceCGAL_1_1parameters.html)

[CGAL::dynamic\_vertex\_property\_t](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__vertex__property__t.html)

## Computing Normals

Methods are provided to compute normals on polygon meshes, either per face or per vertex:

- `CGAL::Polygon_mesh_processing::compute_face_normal()`
- `CGAL::Polygon_mesh_processing::compute_vertex_normal()`

When computing all the normals of faces and vertices, the following functions should be preferred as they factorize some computations:

- `CGAL::Polygon_mesh_processing::compute_face_normals()`
- `CGAL::Polygon_mesh_processing::compute_vertex_normals()`
- `CGAL::Polygon_mesh_processing::compute_normals()`

## Computing Normals Example

In the following examples we associate a normal vector to each vertex and to each face of a mesh of type `CGAL::Surface_mesh`.

**Example:** [Polygon\_mesh\_processing/compute\_normals\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2compute_normals_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/compute\_normal.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include \<iostream>

#include \<string>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef K::Point\_3 Point;

typedef K::Vector\_3 Vector;

typedef [CGAL::Surface\_mesh\<Point>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/eight.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

auto vnormals = mesh.[add\_property\_map](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html#aaff08db9680674e0a16803b77721a356) <vertex\_descriptor, Vector>("v:normal", [CGAL::NULL\_VECTOR](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ga4a98ec6bd9dfd8fe8c46fea553b5d238)).first;

auto fnormals = mesh.add\_property\_map<face\_descriptor, Vector>("f:normal", [CGAL::NULL\_VECTOR](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ga4a98ec6bd9dfd8fe8c46fea553b5d238)).first;

[PMP::compute\_normals](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__normal__grp.html#ga4224769cbbedf39c9e73cb4997744ebf) (mesh, vnormals, fnormals);

std::cout << "Vertex normals:" << std::endl;

for(vertex\_descriptor vd: vertices(mesh))

std::cout << vnormals\[vd\] << std::endl;

std::cout << "Face normals:" << std::endl;

for(face\_descriptor fd: faces(mesh))

std::cout << fnormals\[fd\] << std::endl;

return 0;

}

[CGAL::Surface\_mesh::add\_property\_map](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html#aaff08db9680674e0a16803b77721a356)

std::pair< Property\_map< I, T >, bool > add\_property\_map(std::string name=std::string(), const T t=T())

[CGAL::Polygon\_mesh\_processing::compute\_normals](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__normal__grp.html#ga4224769cbbedf39c9e73cb4997744ebf)

void compute\_normals(const PolygonMesh &pmesh, VertexNormalMap vertex\_normals, FaceNormalMap face\_normals, const NamedParameters &np=parameters::default\_values())

computes the outward unit vector normal for all vertices and faces of the polygon mesh.

**Definition:** compute\_normal.h:901

[CGAL::NULL\_VECTOR](https://doc.cgal.org/latest/Kernel_23/group__kernel__enums.html#ga4a98ec6bd9dfd8fe8c46fea553b5d238)

const CGAL::Null\_vector NULL\_VECTOR

## Computing Curvatures

This package provides methods to compute curvatures on polygon meshes based on "Interpolated Corrected Curvatures on Polyhedral Surfaces" [\[4\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrtc-iccmps-20). This includes mean curvature, Gaussian curvature, principal curvatures and directions. These can be computed on triangle meshes, quad meshes, and meshes with n-gon faces (for n-gons, the centroid must be inside the n-gon face). The algorithms used prove to work well in general. Furthermore, they give accurate results on meshes with noise on vertex positions, under the condition that the correct vertex normals are provided.

It is worth noting that the Principal Curvatures and Directions can also be estimated using the [Estimation of Local Differential Properties of Point-Sampled Surfaces](https://doc.cgal.org/latest/Manual/packages.html#PkgJetFitting3) package, which estimates the local differential quantities of a surface at a point using a local polynomial fitting (fitting a d-jet). Unlike the Interpolated Corrected Curvatures, the Jet Fitting method discards topological information, and thus can be used on point clouds as well.

## Brief Background

Surface curvatures are quantities that describe the local geometry of a surface. They are important in many geometry processing applications. As surfaces are 2-dimensional objects (embedded in 3D), they can bend in 2 independent directions. These directions are called principal directions, and the amount of bending in each direction is called the principal curvature: $k_1$ and $k_2$ (denoting max and min curvatures). Curvature is usually expressed as scalar quantities like the mean curvature $H$ and the Gaussian curvature $K$ which are defined in terms of the principal curvatures.

The algorithms are based on the two papers [\[5\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrt-ccm-22) and [\[4\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrtc-iccmps-20). They introduce a new way to compute curvatures on polygon meshes. The main idea in [\[5\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrt-ccm-22) is based on decoupling the normal information from the position information, which is useful for dealing with digital surfaces, or meshes with noise on vertex positions. [\[4\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrtc-iccmps-20) introduces some extensions to this framework, as it uses linear interpolation on the corrected normal vector field to derive new closed-form equations for the corrected curvature measures. These **interpolated** curvature measures are the first step for computing the curvatures. For a triangle $\tau_{ijk}$, with vertices *i*, *j*, *k:*

\\begin{align\*} \\mu^{(0)}(\\tau\_{ijk}) = &\\frac{1}{2} \\langle \\bar{\\mathbf{u}} \\mid (\\mathbf{x}\_j - \\mathbf{x}\_i) \\times (\\mathbf{x}\_k - \\mathbf{x}\_i) \\rangle, \\\\ \\mu^{(1)}(\\tau\_{ijk}) = &\\frac{1}{2} \\langle \\bar{\\mathbf{u}} \\mid (\\mathbf{u}\_k - \\mathbf{u}\_j) \\times \\mathbf{x}\_i + (\\mathbf{u}\_i - \\mathbf{u}\_k) \\times \\mathbf{x}\_j + (\\mathbf{u}\_j - \\mathbf{u}\_i) \\times \\mathbf{x}\_k \\rangle, \\\\ \\mu^{(2)}(\\tau\_{ijk}) = &\\frac{1}{2} \\langle \\mathbf{u}\_i \\mid \\mathbf{u}\_j \\times \\mathbf{u}\_k \\rangle, \\\\ \\mu^{\\mathbf{X},\\mathbf{Y}}(\\tau\_{ijk}) = & \\frac{1}{2} \\big\\langle \\bar{\\mathbf{u}} \\big| \\langle \\mathbf{Y} | \\mathbf{u}\_k -\\mathbf{u}\_i \\rangle \\mathbf{X} \\times (\\mathbf{x}\_j - \\mathbf{x}\_i) \\big\\rangle -\\frac{1}{2} \\big\\langle \\bar{\\mathbf{u}} \\big| \\langle \\mathbf{Y} | \\mathbf{u}\_j -\\mathbf{u}\_i \\rangle \\mathbf{X} \\times (\\mathbf{x}\_k - \\mathbf{x}\_i) \\big\\rangle, \\end{align\*}

where $\langle \cdot \mid \cdot \rangle$ denotes the scalar product, and $\bar{\mathbf{u}}=\frac{1}{3}( \mathbf{u}_i + \mathbf{u}_j + \mathbf{u}_k )$.

The first measure $\mu^{(0)}$ is the area measure of the triangle, and the measures $\mu^{(1)}$ and $\mu^{(2)}$ are the mean and Gaussian corrected curvature measures of the triangle. The last measure $\mu^{\mathbf{X},\mathbf{Y}}$ is the anisotropic corrected curvature measure of the triangle. The anisotropic measure is later used to compute the principal curvatures and directions through an eigenvalue solver.

The interpolated curvature measures are then computed for each vertex $v$ as the sum of the curvature measures of the faces in a ball around $v$ weighted by the inclusion ratio of the triangle in the ball. This ball radius is an optional (named) parameter of the function. There are 3 cases for the ball radius passed value:

- A positive value is passed: it is naturally used as the radius of the ball.
- 0 is passed, a small epsilon (`average_edge_length * 1e-6`) is used (to account for the convergence of curvatures at infinitely small balls).
- It is not specified (or negative), the sum is instead computed over the incident faces of the vertex $v$.

To get the final curvature value for a vertex $v$, the respective interpolated curvature measure is divided by the interpolated area measure.

$$
\mu^{(k)}( B ) = \sum_{\tau : \text{triangle} } \mu^{(k)}( \tau ) \frac{\mathrm{Area}( \tau \cap B )}{\mathrm{Area}(\tau)}.
$$

## API

The implementation is generic with respect to mesh data structure and can be used with `CGAL::Surface_mesh`, `CGAL::Polyhedron_3`, or any polygon mesh structure meeting the `FaceGraph` concept requirements.

Curvatures are computed for all vertices using `CGAL::Polygon_mesh_processing::interpolated_corrected_curvatures()`, with named parameters to select which curvatures (and directions) to compute. An overload is available for computing curvatures at a single vertex.

## Results

[Figure 76.4](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__icc_measures) illustrates various curvature measures on a triangular mesh.

| ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.040000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-gaussian0.040000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-dmin0.040000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-dmax0.040000-0.000000.jpg) |
| --- | --- | --- | --- |
| (a) | (b) |  |  |

[Figure 76.4](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__icc_measures) Mean curvature, Gaussian curvature, minimal principal curvature direction, and maximal principal curvature direction on a mesh (ball radius set to `0.04`).

| ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.020000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.030000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.040000-0.000000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.050000-0.000000.jpg) |
| --- | --- | --- | --- |
| ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.020000-0.002000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.030000-0.002000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.040000-0.002000.jpg) | ![](https://doc.cgal.org/latest/Polygon_mesh_processing/bimba-mean0.050000-0.002000.jpg) |
| (a) | (b) |  |  |

[Figure 76.5](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__icc_various_ball_radii) Varying the integration ball radius yields a scale space of curvature measures, useful for handling noise in the input mesh. The second row illustrates mean curvature with fixed colormap ranges and ball radii in `{0.02,0.03,0.04,0.05}`.

## Performance

The implemented algorithms exhibit a linear complexity in the number of faces of the mesh. It is worth noting that we pre-computed the vertex normals and passed them as a named parameter to the function to better estimate the performance of the curvature computation. For the data reported in the following table, we used a machine with an Intel Core i7-8750H CPU @ 2.20GHz, 16GB of RAM, on Windows 11, 64 bits and compiled with Visual Studio 2019.

<table><tbody><tr><th>Ball<br>Radius</th><th>Computation</th><th>Spot<br>(6k faces)</th><th>Bunny<br>(144K faces)</th><th>Stanford Dragon<br>(871K faces)</th><th>Old Age or Winter<br>(6M faces)</th></tr><tr><td rowspan="4">vertex<br>1-ring faces<br>(default)</td><td>Mean Curvature</td><td>< 0.001 s</td><td>0.019 s</td><td>0.11 s</td><td>2.68 s</td></tr><tr><td>Gaussian Curvature</td><td>< 0.001 s</td><td>0.017 s</td><td>0.10 s</td><td>2.77 s</td></tr><tr><td>Principal Curvatures & Directions</td><td>0.002 s</td><td>0.044 s</td><td>0.25 s</td><td>3.98 s</td></tr><tr><td>All (optimized for shared computations)</td><td>0.003 s</td><td>0.049 s</td><td>0.28 s</td><td>4.52 s</td></tr><tr><td rowspan="4">r = 0.1<br>* avg_edge_length</td><td>Mean Curvature</td><td>0.017 s</td><td>0.401 s</td><td>2.66 s</td><td>22.29 s</td></tr><tr><td>Gaussian Curvature</td><td>0.018 s</td><td>0.406 s</td><td>2.63 s</td><td>21.61 s</td></tr><tr><td>Principal Curvatures & Directions</td><td>0.019 s</td><td>0.430 s</td><td>2.85 s</td><td>23.55 s</td></tr><tr><td>All (optimized for shared computations)</td><td>0.017 s</td><td>0.428 s</td><td>2.89 s</td><td>24.16 s</td></tr><tr><td rowspan="4">r = 0.5<br>* avg_edge_length</td><td>Mean Curvature</td><td>0.024 s</td><td>0.388 s</td><td>3.18 s</td><td>22.79 s</td></tr><tr><td>Gaussian Curvature</td><td>0.024 s</td><td>0.392 s</td><td>3.21 s</td><td>23.58 s</td></tr><tr><td>Principal Curvatures & Directions</td><td>0.027 s</td><td>0.428 s</td><td>3.41 s</td><td>24.44 s</td></tr><tr><td>All (optimized for shared computations)</td><td>0.025 s</td><td>0.417 s</td><td>3.44 s</td><td>23.93 s</td></tr></tbody></table>

[Figure 76.6](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__icc_performance_table) Performance of the curvature computation on various meshes (in seconds). The first 4 rows show the performance of the default value for the ball radius, which is using the 1-ring of neighboring faces around each vertex, instead of actually approximating the inclusion ratio of the faces in a ball of certain radius. The other rows show a ball radius of `0.1` (and `0.5`) scaled by the average edge length of the mesh. It is clear that using the 1-ring of faces is much faster, but it might not be as effective when used on a noisy input mesh.

[Property Maps](https://doc.cgal.org/latest/BGL/index.html#BGLPropertyMaps) are used to record computed curvatures, as shown in the examples. For each property map, a curvature value is associated with each vertex.

## Interpolated Corrected Curvatures on a Surface Mesh Example

The following example demonstrates computation of curvatures at vertices and storage in property maps provided by `CGAL::Surface_mesh`.

**Example:** [Polygon\_mesh\_processing/interpolated\_corrected\_curvatures\_SM.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2interpolated_corrected_curvatures_SM_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polygon\_mesh\_processing/interpolated\_corrected\_curvatures.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/property\_map.h>

#include <boost/graph/graph\_traits.hpp>

#include \<iostream>

namespace PMP = CGAL::Polygon\_mesh\_processing;

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) Epic\_kernel;

typedef [CGAL::Surface\_mesh<Epic\_kernel::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

int main(int argc, char\* argv\[\])

{

Mesh smesh;

const std::string filename = (argc > 1)?

argv\[1\]:

CGAL::data\_file\_path("meshes/sphere.off");

if (![CGAL::IO::read\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#ga49f5b5e6fbfcbfaaac7604c88e10915c) (filename, smesh))

{

std::cerr << "Invalid input file." << std::endl;

return EXIT\_FAILURE;

}

// creating and tying surface mesh property maps for curvatures (with defaults = 0)

bool created = false;

Mesh::Property\_map<vertex\_descriptor, Epic\_kernel::FT>

mean\_curvature\_map, Gaussian\_curvature\_map;

std::tie(mean\_curvature\_map, created) =

smesh.[add\_property\_map](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html#aaff08db9680674e0a16803b77721a356) <vertex\_descriptor, Epic\_kernel::FT>("v:mean\_curvature\_map", 0);

assert(created);

std::tie(Gaussian\_curvature\_map, created) =

smesh.add\_property\_map<vertex\_descriptor, Epic\_kernel::FT>("v:Gaussian\_curvature\_map", 0);

assert(created);

// we use a tuple of 2 scalar values and 2 vectors for principal curvatures and directions

Mesh::Property\_map<vertex\_descriptor, PMP::Principal\_curvatures\_and\_directions<Epic\_kernel>>

principal\_curvatures\_and\_directions\_map;

std::tie(principal\_curvatures\_and\_directions\_map, created) =

smesh.add\_property\_map<vertex\_descriptor, [PMP::Principal\_curvatures\_and\_directions<Epic\_kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html) >

("v:principal\_curvatures\_and\_directions\_map", { 0, 0,

Epic\_kernel::Vector\_3(0,0,0),

Epic\_kernel::Vector\_3(0,0,0) });

assert(created);

[PMP::interpolated\_corrected\_curvatures](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__corrected__curvatures__grp.html#ga22665c9ce92aaedab07df1b05f20bdb2) (smesh,

CGAL::parameters::vertex\_mean\_curvature\_map(mean\_curvature\_map)

.vertex\_Gaussian\_curvature\_map(Gaussian\_curvature\_map)

.vertex\_principal\_curvatures\_and\_directions\_map(principal\_curvatures\_and\_directions\_map)

// uncomment to use an expansion ball radius of 0.5 to estimate the curvatures

//.ball\_radius(0.5)

);

for (vertex\_descriptor v: vertices(smesh))

{

auto PC = principal\_curvatures\_and\_directions\_map\[v\];

std::cout << v.idx() << ": HC = " << mean\_curvature\_map\[v\]

<< ", GC = " << Gaussian\_curvature\_map\[v\] << "\\n"

<< ", PC = \[ " << PC.min\_curvature << ", " << PC.max\_curvature << " \]\\n";

}

return 0;

}

[CGAL::Polygon\_mesh\_processing::interpolated\_corrected\_curvatures](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__corrected__curvatures__grp.html#ga22665c9ce92aaedab07df1b05f20bdb2)

void interpolated\_corrected\_curvatures(const PolygonMesh &pmesh, const NamedParameters &np=parameters::default\_values())

computes the interpolated corrected curvatures across the mesh pmesh.

**Definition:** interpolated\_corrected\_curvatures.h:1083

[CGAL::IO::read\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#ga49f5b5e6fbfcbfaaac7604c88e10915c)

bool read\_polygon\_mesh(const std::string &fname, Graph &g, const NamedParameters &np=parameters::default\_values())

[CGAL::Polygon\_mesh\_processing::Principal\_curvatures\_and\_directions](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html)

a struct for storing principal curvatures and directions.

**Definition:** interpolated\_corrected\_curvatures.h:43

## Interpolated Corrected Curvatures on a Polyhedron Example

The following example illustrates how to compute the curvatures on vertices and store them in dynamic property maps as the class `CGAL::Polyhedron_3` does not provide storage for the curvatures.

**Example:** [Polygon\_mesh\_processing/interpolated\_corrected\_curvatures\_PH.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2interpolated_corrected_curvatures_PH_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polygon\_mesh\_processing/interpolated\_corrected\_curvatures.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Polyhedron\_3.h>

#include <CGAL/property\_map.h>

#include <boost/graph/graph\_traits.hpp>

#include \<iostream>

#include \<string>

namespace PMP = CGAL::Polygon\_mesh\_processing;

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) Epic\_kernel;

typedef [CGAL::Polyhedron\_3<Epic\_kernel>](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

int main(int argc, char\* argv\[\])

{

Mesh polyhedron;

const std::string filename = (argc > 1)?

argv\[1\]:

CGAL::data\_file\_path("meshes/sphere.off");

if (![CGAL::IO::read\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#ga49f5b5e6fbfcbfaaac7604c88e10915c) (filename, polyhedron))

{

std::cerr << "Invalid input file." << std::endl;

return EXIT\_FAILURE;

}

// define property map to store curvature value and directions

boost::property\_map<Mesh, CGAL::dynamic\_vertex\_property\_t<Epic\_kernel::FT>>::type

mean\_curvature\_map = get([CGAL::dynamic\_vertex\_property\_t<Epic\_kernel::FT>](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__vertex__property__t.html) (), polyhedron),

Gaussian\_curvature\_map = get([CGAL::dynamic\_vertex\_property\_t<Epic\_kernel::FT>](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__vertex__property__t.html) (), polyhedron);

boost::property\_map<Mesh, CGAL::dynamic\_vertex\_property\_t<PMP::Principal\_curvatures\_and\_directions<Epic\_kernel>>>::type

principal\_curvatures\_and\_directions\_map =

get([CGAL::dynamic\_vertex\_property\_t](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__vertex__property__t.html) < [PMP::Principal\_curvatures\_and\_directions<Epic\_kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html) >(), polyhedron);

[PMP::interpolated\_corrected\_curvatures](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__corrected__curvatures__grp.html#ga22665c9ce92aaedab07df1b05f20bdb2) (polyhedron,

CGAL::parameters::vertex\_mean\_curvature\_map(mean\_curvature\_map)

.vertex\_Gaussian\_curvature\_map(Gaussian\_curvature\_map)

.vertex\_principal\_curvatures\_and\_directions\_map(principal\_curvatures\_and\_directions\_map)

// uncomment to use an expansion ball radius of 0.5 to estimate the curvatures

//.ball\_radius(0.5)

);

int i = 0;

for (vertex\_descriptor v: vertices(polyhedron))

{

auto PC = get(principal\_curvatures\_and\_directions\_map, v);

std::cout << i << ": HC = " << get(mean\_curvature\_map, v)

<< ", GC = " << get(Gaussian\_curvature\_map, v) << "\\n"

<< ", PC = \[ " << PC.min\_curvature << ", " << PC.max\_curvature << " \]\\n";

i++;

}

}

## Interpolated Corrected Curvatures on a Vertex Example

The following example demonstrates computation of curvatures at a specific vertex.

**Example:** [Polygon\_mesh\_processing/interpolated\_corrected\_curvatures\_vertex.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2interpolated_corrected_curvatures_vertex_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polygon\_mesh\_processing/interpolated\_corrected\_curvatures.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Surface\_mesh.h>

#include <boost/graph/graph\_traits.hpp>

#include \<iostream>

#include \<string>

namespace PMP = CGAL::Polygon\_mesh\_processing;

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) Epic\_kernel;

typedef [CGAL::Surface\_mesh<Epic\_kernel::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

int main(int argc, char\* argv\[\])

{

// instantiating and reading mesh

Mesh smesh;

const std::string filename = (argc > 1)?

argv\[1\]:

CGAL::data\_file\_path("meshes/sphere.off");

if (![CGAL::IO::read\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#ga49f5b5e6fbfcbfaaac7604c88e10915c) (filename, smesh))

{

std::cerr << "Invalid input file." << std::endl;

return EXIT\_FAILURE;

}

// loop over vertices and use vertex\_descriptor to compute a curvature on one vertex

for (vertex\_descriptor v: vertices(smesh))

{

double h, g;

[PMP::Principal\_curvatures\_and\_directions<Epic\_kernel>](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html) p;

[PMP::interpolated\_corrected\_curvatures](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__corrected__curvatures__grp.html#ga22665c9ce92aaedab07df1b05f20bdb2) (v,

smesh,

CGAL::parameters::vertex\_mean\_curvature(std::ref(h))

.vertex\_Gaussian\_curvature(std::ref(g))

.vertex\_principal\_curvatures\_and\_directions(std::ref(p)));

// we can also specify a ball radius for expansion and a user defined vertex normals map using

// named parameters. Refer to interpolated\_corrected\_curvatures\_SM.cpp to see example usage.

std::cout << v.idx() << ": HC = " << h

<< ", GC = " << g << "\\n"

<< ", PC = \[ " << p.[min\_curvature](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html#a2aef5a24f431e5e33b3356a8bf2aa40f) << ", " << p.[max\_curvature](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html#a92c77d4d5b17d2816bb3b714a4c1d0f5) << " \]\\n";

}

return 0;

}

[CGAL::Polygon\_mesh\_processing::Principal\_curvatures\_and\_directions::min\_curvature](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html#a2aef5a24f431e5e33b3356a8bf2aa40f)

GT::FT min\_curvature

min curvature magnitude

**Definition:** interpolated\_corrected\_curvatures.h:46

[CGAL::Polygon\_mesh\_processing::Principal\_curvatures\_and\_directions::max\_curvature](https://doc.cgal.org/latest/Polygon_mesh_processing/structCGAL_1_1Polygon__mesh__processing_1_1Principal__curvatures__and__directions.html#a92c77d4d5b17d2816bb3b714a4c1d0f5)

GT::FT max\_curvature

max curvature magnitude

**Definition:** interpolated\_corrected\_curvatures.h:49

## Discrete Curvatures

The package also provides methods to compute the standard, non-interpolated discrete mean and Gaussian curvatures on triangle meshes, based on the work of Meyer et al. [\[6\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:mdsb-ddgot-02). These curvatures are computed at each vertex of the mesh, and are based on the angles of the incident triangles. The functions are:

- `CGAL::Polygon_mesh_processing::discrete_mean_curvature()`
- `CGAL::Polygon_mesh_processing::discrete_mean_curvatures()`
- `CGAL::Polygon_mesh_processing::discrete_Gaussian_curvature()`
- `CGAL::Polygon_mesh_processing::discrete_Gaussian_curvatures()`

## Feature Detection

This package provides methods to detect some features of a polygon mesh.

The function `CGAL::Polygon_mesh_processing::sharp_edges_segmentation()` detects sharp edges and deduces surface patches and vertex incidences. It is composed of three functions:

- `CGAL::Polygon_mesh_processing::detect_sharp_edges()`
- `CGAL::Polygon_mesh_processing::connected_components()`
- `CGAL::Polygon_mesh_processing::detect_vertex_incident_patches()`

These functions respectively detect sharp edges, compute patch indices, and assign patch indices to each vertex based on incident faces.

The following example counts the number of edges incident to two faces whose normals form an angle less than 90 degrees, and the number of surface patches separated by these edges.

**Example:** [Polygon\_mesh\_processing/detect\_features\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2detect_features_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/detect\_features.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include \<iostream>

#include \<string>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef [CGAL::Surface\_mesh<K::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/P.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

typedef boost::property\_map<Mesh, CGAL::edge\_is\_feature\_t>::type EIFMap;

typedef boost::property\_map<Mesh, CGAL::face\_patch\_id\_t\<int> >::type PIMap;

typedef boost::property\_map<Mesh, CGAL::vertex\_incident\_patches\_t\<int> >::type VIMap;

EIFMap eif = get(CGAL::edge\_is\_feature, mesh);

PIMap pid = get(CGAL::face\_patch\_id\_t\<int>(), mesh);

VIMap vip = get(CGAL::vertex\_incident\_patches\_t\<int>(), mesh);

std::size\_t number\_of\_patches

\= [PMP::sharp\_edges\_segmentation](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__detect__features__grp.html#gad9cf9f1c459540156fb235a487bebd01) (mesh, 90, eif, pid,

CGAL::parameters::vertex\_incident\_patches\_map(vip));

std::size\_t nb\_sharp\_edges = 0;

for(boost::graph\_traits\<Mesh>::edge\_descriptor e: edges(mesh))

{

if(get(eif, e))

++nb\_sharp\_edges;

}

std::cout << "This mesh contains " << nb\_sharp\_edges << " sharp edges" << std::endl;

std::cout << " and " << number\_of\_patches << " surface patches." << std::endl;

return 0;

}

[CGAL::Polygon\_mesh\_processing::sharp\_edges\_segmentation](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__detect__features__grp.html#gad9cf9f1c459540156fb235a487bebd01)

boost::graph\_traits< PolygonMesh >::faces\_size\_type sharp\_edges\_segmentation(const PolygonMesh &pmesh, FT angle\_in\_deg, EdgeIsFeatureMap edge\_is\_feature\_map, PatchIdMap patch\_id\_map, const NamedParameters &np=parameters::default\_values())

This function calls successively CGAL::Polygon\_mesh\_processing::detect\_sharp\_edges(),...

**Definition:** detect\_features.h:460

## Hausdorff Distance

This package provides methods to compute (approximate) distances between meshes and point sets.

## Approximate Hausdorff Distance

The function [`approximate_Hausdorff_distance()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga74376aa81d44d745426acfad5a0ac8de) computes an approximation of the Hausdorff distance from a mesh `tm1` to a mesh `tm2`. Given a a sampling of `tm1`, it computes the distance to `tm2` of the farthest sample point to `tm2` [\[3\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cignoni1998metro). The symmetric version ([`approximate_symmetric_Hausdorff_distance()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga035fdbf660615b036cb3f47f7997b739)) is the maximum of the two non-symmetric distances. Internally, points are sampled using [`sample_triangle_mesh()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga6307a4504382c46dc3b0e578ca1f7a3b) and the distance to each sample point is computed using [`max_distance_to_triangle_mesh()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#gaed9454c6ed046cd4fb7928cf2b5f7c2c). The quality of the approximation depends on the quality of the sampling and the runtime depends on the number of sample points. Three sampling methods with different parameters are provided (see [Figure 76.7](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__sampling_bunny)).

![](https://doc.cgal.org/latest/Polygon_mesh_processing/pmp_sampling_bunny.jpg)

[Figure 76.7](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#fig__sampling_bunny) Sampling of a triangle mesh using different sampling methods. From left to right: (a) Grid sampling, (b) Monte-Carlo sampling with fixed number of points per face and per edge, (c) Monte-Carlo sampling with a number of points proportional to the area/length, and (d) Uniform random sampling. The four pictures represent the sampling on the same portion of a mesh, parameters were adjusted so that the total number of points sampled in faces (blue points) and on edges (red points) are roughly the same. Note that when using the random uniform sampling some faces/edges may not contain any point, but this method is the only one that allows to exactly match a given number of points.

The function [`approximate_max_distance_to_point_set()`](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga3451246234c24dd4f03d17fc17d50336) computes an approximation of the Hausdorff distance from a mesh to a point set. For each triangle, lower and upper bounds of the Hausdorff distance to the point set are computed. Triangles are refined until the difference between bounds is below a user-defined precision threshold.

### Approximate Hausdorff Distance Example

In the following example, a mesh is isotropically remeshed and the approximate distance between the input and the output is computed.

**Example:** [PMP\_Remeshing/hausdorff\_distance\_remeshing\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/PMP_Remeshing_2hausdorff_distance_remeshing_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/distance.h>

#include <CGAL/Polygon\_mesh\_processing/remesh.h>

#define TAG CGAL::Parallel\_if\_available\_tag

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef K::Point\_3 Point;

typedef [CGAL::Surface\_mesh<K::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int, char\*\*)

{

Mesh tm1, tm2;

[CGAL::make\_tetrahedron](https://doc.cgal.org/latest/BGL/group__PkgBGLGeneratorFct.html#ga92116dc89384a0b8d565e2411f1c173a) (Point(.0,.0,.0),

Point(2,.0,.0),

Point(1,1,1),

Point(1,.0,2),

tm1);

tm2 = tm1;

[CGAL::Polygon\_mesh\_processing::isotropic\_remeshing](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__local__remeshing__grp.html#ga412f696ec3009074bf957f1bba638248) (tm2.faces(),.05, tm2);

std::cout << "Approximated Hausdorff distance: "

<< [CGAL::Polygon\_mesh\_processing::approximate\_Hausdorff\_distance](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga74376aa81d44d745426acfad5a0ac8de)

\<TAG>(tm1, tm2, CGAL::parameters::number\_of\_points\_per\_area\_unit(4000))

<< std::endl;

return 0;

}

[CGAL::Polygon\_mesh\_processing::approximate\_Hausdorff\_distance](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga74376aa81d44d745426acfad5a0ac8de)

double approximate\_Hausdorff\_distance(const TriangleMesh &tm1, const TriangleMesh &tm2, const NamedParameters1 &np1=parameters::default\_values(), const NamedParameters2 &np2=parameters::default\_values())

computes the approximate Hausdorff distance from tm1 to tm2 by returning the distance of the farthest...

**Definition:** distance.h:1174

[CGAL::make\_tetrahedron](https://doc.cgal.org/latest/BGL/group__PkgBGLGeneratorFct.html#ga92116dc89384a0b8d565e2411f1c173a)

boost::graph\_traits< Graph >::halfedge\_descriptor make\_tetrahedron(const P &p0, const P &p1, const P &p2, const P &p3, Graph &g)

### Max Distance Between Point Set and Surface Example

In [Poisson\_surface\_reconstruction\_3/poisson\_reconstruction\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Poisson_surface_reconstruction_3_2poisson_reconstruction_example_8cpp-example.html), a triangulated surface mesh is constructed from a point set using the [Poisson reconstruction algorithm](https://doc.cgal.org/latest/Manual/packages.html#PkgPoissonSurfaceReconstruction3) , and the distance between the point set and the reconstructed surface is computed as follows:

// computes the approximation error of the reconstruction

double max\_dist =

[CGAL::Polygon\_mesh\_processing::approximate\_max\_distance\_to\_point\_set](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga3451246234c24dd4f03d17fc17d50336)

(output\_mesh,

CGAL::make\_range (boost::make\_transform\_iterator

(points.begin(), [CGAL::Property\_map\_to\_unary\_function<Point\_map>](https://doc.cgal.org/latest/Property_map/structCGAL_1_1Property__map__to__unary__function.html) ()),

boost::make\_transform\_iterator

(points.end(), [CGAL::Property\_map\_to\_unary\_function<Point\_map>](https://doc.cgal.org/latest/Property_map/structCGAL_1_1Property__map__to__unary__function.html) ())),

4000);

std::cout << "Max distance to point\_set: " << max\_dist << std::endl;

[CGAL::Polygon\_mesh\_processing::approximate\_max\_distance\_to\_point\_set](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__distance__grp.html#ga3451246234c24dd4f03d17fc17d50336)

double approximate\_max\_distance\_to\_point\_set(const TriangleMesh &tm, const PointRange &points, const double precision, const NamedParameters &np=parameters::default\_values())

returns an approximation of the distance between points and the point lying on tm that is the farthes...

**Definition:** distance.h:1253

[CGAL::Property\_map\_to\_unary\_function](https://doc.cgal.org/latest/Property_map/structCGAL_1_1Property__map__to__unary__function.html)

## Bounded Hausdorff Distance

The function `CGAL::Polygon_mesh_processing::bounded_error_Hausdorff_distance()` computes an estimate of the Hausdorff distance of two triangle meshes which is bounded by a user-given error bound. Given two meshes `tm1` and `tm2`, it follows the procedure given by [\[7\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_tang2009interactive). Namely, a bounded volume hierarchy (BVH) is built on `tm1` and `tm2` respectively. The BVH on `tm1` is used to iterate over all triangles in `tm1`. Throughout the traversal, the procedure keeps track of a global lower and upper bound on the Hausdorff distance respectively. For each triangle `t` in `tm1`, by traversing the BVH on `tm2`, it is estimated via the global bounds whether `t` can still contribute to the actual Hausdorff distance. From this process, a set of candidate triangles is selected.

The candidate triangles are subsequently subdivided and for each smaller triangle, the BVH on `tm2` is traversed again. This is repeated until the triangle is smaller than the user-given error bound, all vertices of the triangle are projected onto the same triangle in `tm2`, or the triangle's upper bound is lower than the global lower bound. After creation, the subdivided triangles are added to the list of candidate triangles. Thereby, all candidate triangles are processed until a triangle is found in which the Hausdorff distance is realized or in which it is guaranteed to be realized within the user-given error bound.

In the current implementation, the BVH used is an AABB-tree and not the swept sphere volumes as used in the original implementation. This should explain the runtime difference observed with the original implementation.

The function `CGAL::Polygon_mesh_processing::bounded_error_Hausdorff_distance()` computes the one-sided Hausdorff distance from `tm1` to `tm2`. This component also provides the symmetric distance `CGAL::Polygon_mesh_processing::bounded_error_symmetric_Hausdorff_distance()` and a utility function called `CGAL::Polygon_mesh_processing::is_Hausdorff_distance_larger()` that returns `true` if the Hausdorff distance between two meshes is larger than the user-defined max distance.

### Bounded Hausdorff Distance Example

In the following examples: (a) the distance of a tetrahedron to a remeshed version of itself is computed, (b) the distance of two geometries is computed which is realized strictly in the interior of a triangle of the first geometry, (c) a perturbation of a user-given mesh is compared to the original user-given mesh, (d) two user-given meshes are compared, where the second mesh is gradually moved away from the first one.

**Example:** [Polygon\_mesh\_processing/hausdorff\_bounded\_error\_distance\_example.cpp](https://doc.cgal.org/latest/Polygon_mesh_processing/Polygon_mesh_processing_2hausdorff_bounded_error_distance_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/IO/OFF.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polyhedron\_3.h>

#include <CGAL/Polygon\_mesh\_processing/remesh.h>

#include <CGAL/Polygon\_mesh\_processing/distance.h>

#include <CGAL/Polygon\_mesh\_processing/transform.h>

using [Kernel](https://doc.cgal.org/latest/Kernel_23/namespaceKernel.html) = [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html);

using FT = typename Kernel::FT;

using [Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) = typename [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html);

using [Vector\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Vector__3.html) = typename [Kernel::Vector\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Vector__3.html);

using Affine\_transformation\_3 = typename Kernel::Aff\_transformation\_3;

using TAG = [CGAL::Sequential\_tag](https://doc.cgal.org/latest/STL_Extension/structCGAL_1_1Sequential__tag.html);

using Surface\_mesh = [CGAL::Surface\_mesh<Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html);

using Polyhedron = [CGAL::Polyhedron\_3\<Kernel>](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html);

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\*\* argv) {

const double error\_bound = 1e-4;

const std::string filepath = (argc > 1? argv\[1\]: CGAL::data\_file\_path("meshes/blobby.off"));

// We create a tetrahedron, remesh it, and compute the distance.

// The expected distance is error\_bound.

std::cout << std::endl << "\* remeshing tetrahedron example:" << std::endl;

Surface\_mesh mesh1, mesh2;

[CGAL::make\_tetrahedron](https://doc.cgal.org/latest/BGL/group__PkgBGLGeneratorFct.html#ga92116dc89384a0b8d565e2411f1c173a) (

[Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) (0, 0, 0), [Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) (2, 0, 0),

[Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) (1, 1, 1), [Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) (1, 0, 2), mesh1);

mesh2 = mesh1;

using edge\_descriptor = typename boost::graph\_traits<Surface\_mesh>::edge\_descriptor;

Surface\_mesh::Property\_map<edge\_descriptor, bool> is\_constrained\_map =

mesh2.add\_property\_map<edge\_descriptor, bool>("e:is\_constrained", true).first;

const double target\_edge\_length = 0.05;

[PMP::isotropic\_remeshing](https://doc.cgal.org/latest/PMP_Remeshing/group__PMP__local__remeshing__grp.html#ga412f696ec3009074bf957f1bba638248) (

mesh2.faces(), target\_edge\_length, mesh2,

CGAL::parameters::edge\_is\_constrained\_map(is\_constrained\_map));

std::cout << "\* one-sided bounded-error Hausdorff distance: " <<

PMP::bounded\_error\_Hausdorff\_distance\<TAG>(mesh1, mesh2, error\_bound) << std::endl;

// We load a mesh, save it in two different containers, and

// translate the second mesh by 1 unit. The expected distance is 1.

std::cout << std::endl << "\* moving mesh example:" << std::endl;

Surface\_mesh surface\_mesh;

[CGAL::IO::read\_OFF](https://doc.cgal.org/latest/BGL/group__PkgBGLIoFuncsOFF.html#gadd0f59b6789ef565bb7e95f3d0d89e91) (filepath, surface\_mesh);

Polyhedron polyhedron;

[CGAL::IO::read\_OFF](https://doc.cgal.org/latest/BGL/group__PkgBGLIoFuncsOFF.html#gadd0f59b6789ef565bb7e95f3d0d89e91) (filepath, polyhedron);

[PMP::transform](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__misc__grp.html#gaf2cbaecebb112bc4857782728481ccec) (Affine\_transformation\_3([CGAL::Translation](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Translation.html) (),

[Vector\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Vector__3.html) (FT(0), FT(0), FT(1))), polyhedron);

std::cout << "\* symmetric bounded-error Hausdorff distance: " <<

PMP::bounded\_error\_symmetric\_Hausdorff\_distance\<TAG>(surface\_mesh, polyhedron, error\_bound)

<< std::endl << std::endl;

return EXIT\_SUCCESS;

}

[CGAL::Translation](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Translation.html)

[Kernel::Vector\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Vector__3.html)

[CGAL::Polygon\_mesh\_processing::transform](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__misc__grp.html#gaf2cbaecebb112bc4857782728481ccec)

void transform(const Transformation &transformation, PolygonMesh &mesh, const NamedParameters &np=parameters::default\_values())

applies a transformation to every vertex of a PolygonMesh.

**Definition:** transform.h:50

[CGAL::Sequential\_tag](https://doc.cgal.org/latest/STL_Extension/structCGAL_1_1Sequential__tag.html)

## Implementation History

A first version of this package was started by Ilker O. Yaz and Sébastien Loriot. Jane Tournois worked on the finalization of the API, code, and documentation.

The polyhedral envelope containment check was integrated in CGAL 5.3. The implementation makes use of the version of [https://github.com/wangbolun300/fast-envelope](https://github.com/wangbolun300/fast-envelope) available on 7th of October 2020. It only uses the high level algorithm of checking that a query is covered by a set of prisms, where each prism is an offset for an input triangle. That is, the implementation in CGAL does not use indirect predicates.

Interpolated corrected curvatures were implemented during GSoC 2022 by Hossam Saeed, supervised by David Coeurjolly, Jacques-Olivier Lachaud, and Sébastien Loriot. The implementation is based on [\[4\]](https://doc.cgal.org/latest/Polygon_mesh_processing/citelist.html#CITEREF_cgal:lrtc-iccmps-20). [DGtal's implementation](https://dgtal-team.github.io/doc-nightly/moduleCurvatureMeasures.html) was also referenced during development.