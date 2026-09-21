CGAL 6.2.1 - Polygon Mesh Repair

Searching...

No Matches

![](https://doc.cgal.org/latest/PMP_Mesh_repair/neptun_head.jpg)

## Introduction

Geometric models, whether acquired through imprecise tools or imperfect processes, frequently exhibit defects such as inconsistent orientations, degeneracies, gaps, missing data, non-manifold features, or self-intersections.

This CGAL package provides a comprehensive set of functions to detect and address both combinatorial and geometric defects. The first part of this documentation focuses on combinatorial repairs, with particular attention to orienting and repairing polygon soups—a necessary step to obtain a valid combinatorial polygon mesh structure. The second part describes functions for geometric repairs, such as removing nearly degenerate faces, or filling holes.

## Orientation

This package offers multiple functions to compute consistent face orientations for set of faces (Section [Polygon Soups](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#PMPPolygonSoups)) and polygon meshes (see Section [Polygon Meshes](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#OrientingPolygonMeshes)).

## Polygon Soups

When the faces of a polygon mesh are given but the connectivity is unknown, this set of faces is called a *polygon soup*.

Before running any of the algorithms on a polygon soup, one should ensure that the polygons are consistently oriented. To do so, this package provides the function `CGAL::Polygon_mesh_processing::orient_polygon_soup()`, described in [\[1\]](https://doc.cgal.org/latest/PMP_Mesh_repair/citelist.html#CITEREF_gueziec2001cutting).

To deal with polygon soups that cannot be converted to a combinatorially manifold surface, some points must be duplicated. Because a polygon soup does not have any connectivity (each point has as many occurrences as the number of polygons it belongs to), duplicating one point (or a pair of points) amounts to duplicating the polygon to which it belongs. The duplicated points are either an endpoint of an edge incident to more than two polygons, an endpoint of an edge between two polygons with incompatible orientations (during the re-orientation process), or more generally a point *p* at which the intersection of an infinitesimally small ball centered at *p* with the polygons incident to it is not a topological disk.

Once the polygon soup is consistently oriented, possibly with duplicated points, connectivity can be recovered and made consistent to build a valid polygon mesh. The function `CGAL::Polygon_mesh_processing::polygon_soup_to_polygon_mesh()` performs this mesh construction step.

**Example:** [PMP\_Mesh\_repair/orient\_polygon\_soup\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2orient_polygon_soup_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedron\_3.h>

#include <CGAL/Polyhedron\_items\_with\_id\_3.h>

#include <CGAL/Polygon\_mesh\_processing/orient\_polygon\_soup.h>

#include <CGAL/Polygon\_mesh\_processing/polygon\_soup\_to\_polygon\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/orientation.h>

#include <CGAL/IO/polygon\_soup\_io.h>

#include \<fstream>

#include \<iostream>

#include \<string>

#include \<vector>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef [CGAL::Polyhedron\_3<K, CGAL::Polyhedron\_items\_with\_id\_3>](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html) Mesh;

// Optional visitor for orientating a polygon soup to demonstrate usage for some functions.

// inherits from the default class as some functions are not overloaded

struct Visitor: public [CGAL::Polygon\_mesh\_processing::Default\_orientation\_visitor](https://doc.cgal.org/latest/PMP_Mesh_repair/structCGAL_1_1Polygon__mesh__processing_1_1Default__orientation__visitor.html)

{

void non\_manifold\_edge(std::size\_t id1, std::size\_t id2, std::size\_t nb\_poly)

{

std::cout << "The edge " << id1 << ", " << id2 << " is not manifold: " << nb\_poly << " incident polygons." << std::endl;

}

void non\_manifold\_vertex(std::size\_t id, std::size\_t nb\_cycles)

{

std::cout << "The vertex " << id << " is not manifold: " << nb\_cycles << " connected components of vertices in the link." << std::endl;

}

void duplicated\_vertex(std::size\_t v1, std::size\_t v2)

{

std::cout << "The vertex " << v1 << " has been duplicated, its new id is " << v2 << "." << std::endl;

}

void vertex\_id\_in\_polygon\_replaced(std::size\_t p\_id, std::size\_t i1, std::size\_t i2)

{

std::cout << "In the polygon " << p\_id << ", the index " << i1 << " has been replaced by " << i2 << "." << std::endl;

}

void polygon\_orientation\_reversed(std::size\_t p\_id)

{

std::cout << "The polygon " << p\_id << " has been reversed." << std::endl;

}

};

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/tet-shuffled.off");

std::vector<K::Point\_3> points;

std::vector<std::vector<std::size\_t> > polygons;

if(![CGAL::IO::read\_polygon\_soup](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#gaafb0e02f4669802c727709743065804c) (filename, points, polygons) || points.empty())

{

std::cerr << "Cannot open file " << std::endl;

return EXIT\_FAILURE;

}

Visitor visitor;

[CGAL::Polygon\_mesh\_processing::orient\_polygon\_soup](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gad380465ee62d858d27fab4cfda6c1764) (points, polygons, CGAL::parameters::visitor(visitor));

Mesh mesh;

[CGAL::Polygon\_mesh\_processing::polygon\_soup\_to\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga2ba9722ec8472a1455107ffce7145e46) (points, polygons, mesh);

// Number the faces because 'orient\_to\_bound\_a\_volume' needs a face <--> index map

int index = 0;

for(Mesh::Face\_iterator fb=mesh.facets\_begin(), fe=mesh.facets\_end(); fb!=fe; ++fb)

fb->id() = index++;

if([CGAL::is\_closed](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gae04c8044cf1eee6a84baa5b79ab99fef) (mesh))

[CGAL::Polygon\_mesh\_processing::orient\_to\_bound\_a\_volume](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gadf6efc8f4475792ccafe36f3e8734302) (mesh);

std::ofstream out("tet-oriented1.off");

out.precision(17);

out << mesh;

out.close();

[CGAL::Polygon\_mesh\_processing::reverse\_face\_orientations](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gad8a3439883e3e76651f96d15ba58b2bc) (mesh);

std::ofstream out2("tet-oriented2.off");

out2.precision(17);

out2 << mesh;

out2.close();

return EXIT\_SUCCESS;

}

[CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html)

[CGAL::Polyhedron\_3](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html)

[CGAL::IO::read\_polygon\_soup](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#gaafb0e02f4669802c727709743065804c)

bool read\_polygon\_soup(const std::string &fname, PointRange &points, PolygonRange &polygons, const NamedParameters &np=parameters::default\_values())

[CGAL::Polygon\_mesh\_processing::polygon\_soup\_to\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga2ba9722ec8472a1455107ffce7145e46)

void polygon\_soup\_to\_polygon\_mesh(const PointRange &points, const PolygonRange &polygons, PolygonMesh &out, const NamedParameters\_PS &np\_ps=parameters::default\_values(), const NamedParameters\_PM &np\_pm=parameters::default\_values())

builds a polygon mesh from a soup of polygons.

**Definition:** polygon\_soup\_to\_polygon\_mesh.h:330

[CGAL::Polygon\_mesh\_processing::orient\_polygon\_soup](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gad380465ee62d858d27fab4cfda6c1764)

bool orient\_polygon\_soup(PointRange &points, PolygonRange &polygons, const NamedParameters &np=parameters::default\_values())

tries to consistently orient a soup of polygons in 3D space.

**Definition:** orient\_polygon\_soup.h:543

[CGAL::Polygon\_mesh\_processing::reverse\_face\_orientations](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gad8a3439883e3e76651f96d15ba58b2bc)

void reverse\_face\_orientations(PolygonMesh &pmesh)

reverses for each face the order of the vertices along the face boundary.

**Definition:** orientation.h:274

[CGAL::Polygon\_mesh\_processing::orient\_to\_bound\_a\_volume](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#gadf6efc8f4475792ccafe36f3e8734302)

void orient\_to\_bound\_a\_volume(TriangleMesh &tm, const NamedParameters &np=parameters::default\_values())

orients the connected components of tm to make it bound a volume.

**Definition:** orientation.h:1347

[CGAL::is\_closed](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gae04c8044cf1eee6a84baa5b79ab99fef)

bool is\_closed(const FaceGraph &g)

[CGAL::Polygon\_mesh\_processing::Default\_orientation\_visitor](https://doc.cgal.org/latest/PMP_Mesh_repair/structCGAL_1_1Polygon__mesh__processing_1_1Default__orientation__visitor.html)

Default visitor model of PMPPolygonSoupOrientationVisitor.

**Definition:** orient\_polygon\_soup.h:50

Inversely, a polygon soup can be constructed from a polygon mesh, using the function `CGAL::Polygon_mesh_processing::polygon_mesh_to_polygon_soup()`.

## Polygon Meshes

This package provides functions for orienting faces in a closed polygon mesh:

- `CGAL::Polygon_mesh_processing::orient()` orients each connected component of a closed polygon mesh outward or inward.
- `CGAL::Polygon_mesh_processing::orient_to_bound_a_volume()` orients the connected components of a closed polygon mesh so that they bound a volume (see [Definitions](https://doc.cgal.org/latest/PMP_Boolean_operations/index.html#coref_def_subsec) for a precise definition).
- `CGAL::Polygon_mesh_processing::is_outward_oriented()` checks whether an oriented polygon mesh is oriented such that the normals to all faces point outward from the domain bounded by the mesh.
- `CGAL::Polygon_mesh_processing::reverse_face_orientations()` reverses the orientation of halfedges around faces, thereby reversing the computed normals (see Section [Computing Normals](https://doc.cgal.org/latest/Polygon_mesh_processing/index.html#PMPNormalComp)).
- `CGAL::Polygon_mesh_processing::volume_connected_components()` provides information about the 3D arrangement of surface connected components in a triangle mesh, with many named parameter options, making it a generalization of `is_outward_oriented()`.
- `CGAL::Polygon_mesh_processing::duplicate_non_manifold_edges_in_polygon_soup()` duplicates points and edges to make a soup orientable, without altering face orientations.
- `CGAL::Polygon_mesh_processing::orient_triangle_soup_with_reference_triangle_mesh()` orients the triangles of a soup according to a reference mesh.
- `CGAL::Polygon_mesh_processing::merge_reversible_connected_components()` merges the connected components of a polygon mesh when possible.

The following example demonstrates how to repair and orient a soup to obtain a mesh from a reference:

**Example:** [PMP\_Mesh\_repair/orientation\_pipeline\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2orientation_pipeline_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/orientation.h>

#include <CGAL/Polygon\_mesh\_processing/polygon\_soup\_to\_polygon\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/orient\_polygon\_soup\_extension.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/algorithm.h>

#include <CGAL/Timer.h>

#include <CGAL/IO/polygon\_soup\_io.h>

#include \<algorithm>

#include \<cstdlib>

#include \<iostream>

#include \<string>

#include \<vector>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef K::Point\_3 Point\_3;

typedef [CGAL::Surface\_mesh<Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\*\* argv)

{

const std::string input\_filename = (argc < 2)? CGAL::data\_file\_path("meshes/blobby-shuffled.off"): argv\[1\];

const std::string reference\_filename = (argc < 2)? CGAL::data\_file\_path("meshes/blobby.off"): argv\[2\];

std::vector<Point\_3> points;

std::vector<std::vector<std::size\_t> > polygons;

if(![CGAL::IO::read\_polygon\_soup](https://doc.cgal.org/latest/Stream_support/group__IOstreamFunctions.html#gaafb0e02f4669802c727709743065804c) (input\_filename, points, polygons) ||

points.size() == 0 || polygons.size() == 0)

{

std::cerr << "Error: can not read input file.\\n";

return 1;

}

Mesh ref1;

if(!PMP::IO::read\_polygon\_mesh(reference\_filename, ref1))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

std::cout << "Is the soup a polygon mesh?: " << [PMP::is\_polygon\_soup\_a\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga8b9d12d817b5cc76f5a42d74eac75bf3) (polygons) << std::endl;

PMP::orient\_triangle\_soup\_with\_reference\_triangle\_mesh<CGAL::Sequential\_tag>(ref1, points, polygons);

std::cout << "And now?: " << [PMP::is\_polygon\_soup\_a\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga8b9d12d817b5cc76f5a42d74eac75bf3) (polygons) << std::endl;

[PMP::duplicate\_non\_manifold\_edges\_in\_polygon\_soup](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#ga2aa4f7b500dc51d1fc4747705a050946) (points, polygons);

std::cout << "And now?: " << [PMP::is\_polygon\_soup\_a\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga8b9d12d817b5cc76f5a42d74eac75bf3) (polygons) << std::endl;

Mesh poly;

[PMP::polygon\_soup\_to\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga2ba9722ec8472a1455107ffce7145e46) (points, polygons, poly);

typedef boost::property\_map<Mesh, CGAL::dynamic\_face\_property\_t<std::size\_t> >::type Fccmap;

Fccmap fccmap = get([CGAL::dynamic\_face\_property\_t<std::size\_t>](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__face__property__t.html) (), poly);

std::cout << [PMP::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9) (poly, fccmap) << " CCs before merge." << std::endl;

[PMP::merge\_reversible\_connected\_components](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#ga10325d30c17096eed40938545b53cb14) (poly);

std::cout<< [PMP::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9) (poly, fccmap) << " remaining CCs." << std::endl;

return 0;

}

[CGAL::Surface\_mesh](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html)

[CGAL::Polygon\_mesh\_processing::is\_polygon\_soup\_a\_polygon\_mesh](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga8b9d12d817b5cc76f5a42d74eac75bf3)

bool is\_polygon\_soup\_a\_polygon\_mesh(const PolygonRange &polygons)

returns true if the soup of polygons defines a valid polygon mesh that can be handled by CGAL::Polygo...

**Definition:** polygon\_soup\_to\_polygon\_mesh.h:195

[CGAL::Polygon\_mesh\_processing::connected\_components](https://doc.cgal.org/latest/Polygon_mesh_processing/group__PMP__keep__connected__components__grp.html#ga239704e9a2752ed67d361be55acf3bf9)

boost::property\_traits< FaceComponentMap >::value\_type connected\_components(const PolygonMesh &pmesh, FaceComponentMap fcm, const NamedParameters &np=parameters::default\_values())

[CGAL::Polygon\_mesh\_processing::merge\_reversible\_connected\_components](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#ga10325d30c17096eed40938545b53cb14)

void merge\_reversible\_connected\_components(PolygonMesh &pm, const NamedParameters &np=parameters::default\_values())

reverses the connected components of tm having compatible boundary cycles that could be merged if the...

**Definition:** orientation.h:1456

[CGAL::Polygon\_mesh\_processing::duplicate\_non\_manifold\_edges\_in\_polygon\_soup](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__orientation__grp.html#ga2aa4f7b500dc51d1fc4747705a050946)

bool duplicate\_non\_manifold\_edges\_in\_polygon\_soup(PointRange &points, PolygonRange &polygons)

duplicates each point p at which the intersection of an infinitesimally small ball centered at p with...

**Definition:** orient\_polygon\_soup\_extension.h:65

[CGAL::dynamic\_face\_property\_t](https://doc.cgal.org/latest/BGL/structCGAL_1_1dynamic__face__property__t.html)

## Combinatorial Repair

## Polygon Soup Repairing

To ensure that a polygon soup can be oriented (see Section [Polygon Soups](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#PMPPolygonSoups)) and transformed into a usable polygon mesh, it might be necessary to preprocess the data to remove combinatorial and geometrical errors. This package offers the following functions:

- `CGAL::Polygon_mesh_processing::merge_duplicate_points_in_polygon_soup()`,
- `CGAL::Polygon_mesh_processing::merge_duplicate_polygons_in_polygon_soup()`,
- `CGAL::Polygon_mesh_processing::remove_isolated_points_in_polygon_soup()`,

as well as the function `CGAL::Polygon_mesh_processing::repair_polygon_soup()`, which bundles the previous functions and an additional handful of repairing techniques to obtain an as-clean-as-possible polygon soup.

## Stitching

When handling polygon meshes, it might happen that a mesh has several edges and vertices that are duplicated. For those edges and vertices, the connectivity of the mesh is incomplete, if not considered incorrect.

Stitching the borders of a polygon mesh can be done to fix some of the duplication. It consists in two main steps. First, border edges that are geometrically identical but duplicated are detected and paired. Then, they are "stitched" together so that edges and vertices duplicates are removed from the mesh, and each of these remaining edges is incident to exactly two faces.

The functions `CGAL::Polygon_mesh_processing::stitch_boundary_cycle()`, `CGAL::Polygon_mesh_processing::stitch_boundary_cycles()`, and `CGAL::Polygon_mesh_processing::stitch_borders()` can perform such repairing operations: the first two functions can be used to stitch halfedges that are part of the same boundary(ies), whereas the third function is more generic and can also stitch halfedges that live on different borders.

The input mesh should represent a manifold surface; otherwise, stitching may not succeed.

### Stitching Example

The following example applies the stitching operation to a simple quad mesh with duplicated border edges.

**Example:** [PMP\_Mesh\_repair/stitch\_borders\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2stitch_borders_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polyhedron\_3.h>

#include <CGAL/Polygon\_mesh\_processing/stitch\_borders.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include \<iostream>

#include \<string>

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef [CGAL::Polyhedron\_3\<K>](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html) Mesh;

namespace PMP = CGAL::Polygon\_mesh\_processing;

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/quads\_to\_stitch.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

std::cout << "Before stitching: " << std::endl;

std::cout << "\\t Number of vertices:\\t" << mesh.[size\_of\_vertices](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html#ad661d362a8e515d67108803796eabac8) () << std::endl;

std::cout << "\\t Number of halfedges:\\t" << mesh.size\_of\_halfedges() << std::endl;

std::cout << "\\t Number of facets:\\t" << mesh.size\_of\_facets() << std::endl;

[PMP::stitch\_borders](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#gaa0ca177eb85fafc4be1f88c5b27c25bd) (mesh);

std::cout << "Stitching done: " << std::endl;

std::cout << "\\t Number of vertices:\\t" << mesh.size\_of\_vertices() << std::endl;

std::cout << "\\t Number of halfedges:\\t" << mesh.size\_of\_halfedges() << std::endl;

std::cout << "\\t Number of facets:\\t" << mesh.size\_of\_facets() << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) ("mesh\_stitched.off", mesh, CGAL::parameters::stream\_precision(17));

return 0;

}

[CGAL::Polyhedron\_3::size\_of\_vertices](https://doc.cgal.org/latest/Polyhedron/classCGAL_1_1Polyhedron__3.html#ad661d362a8e515d67108803796eabac8)

size\_type size\_of\_vertices() const

[CGAL::Polygon\_mesh\_processing::stitch\_borders](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#gaa0ca177eb85fafc4be1f88c5b27c25bd)

std::size\_t stitch\_borders(PolygonMesh &pmesh, const HalfedgePairsRange &hedge\_pairs\_to\_stitch, const NamedParameters &np=parameters::default\_values())

stitches together border halfedges in a polygon mesh.

**Definition:** stitch\_borders.h:1306

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66)

bool write\_polygon\_mesh(const std::string &fname, Graph &g, const NamedParameters &np=parameters::default\_values())

## Polygon Mesh Manifoldness

Non-manifold vertices can be detected using the function `CGAL::Polygon_mesh_processing::is_non_manifold_vertex()`. The function `CGAL::Polygon_mesh_processing::duplicate_non_manifold_vertices()` can be used to attempt to create a combinatorially manifold surface mesh by splitting any non-manifold vertex into as many vertices as there are manifold sheets at this geometric position. Note however that the mesh will still not be manifold from a geometric point of view, as the positions of the new vertices introduced at a non-manifold vertex are identical to the input non-manifold vertex.

### Manifoldness Repair Example

In the following example, a non-manifold configuration is artificially created and fixed with the help of the functions described above.

**Example:** [PMP\_Mesh\_repair/manifoldness\_repair\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2manifoldness_repair_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/Polygon\_mesh\_processing/repair.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/boost/graph/iterator.h>

#include \<iostream>

#include \<iterator>

#include \<string>

#include \<vector>

namespace PMP = CGAL::Polygon\_mesh\_processing;

namespace NP = [CGAL::parameters](https://doc.cgal.org/latest/STL_Extension/namespaceCGAL_1_1parameters.html);

typedef [CGAL::Exact\_predicates\_inexact\_constructions\_kernel](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Exact__predicates__inexact__constructions__kernel.html) K;

typedef [CGAL::Surface\_mesh<K::Point\_3>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef boost::graph\_traits\<Mesh>::halfedge\_descriptor halfedge\_descriptor;

void merge\_vertices(vertex\_descriptor v\_keep, vertex\_descriptor v\_rm, Mesh& mesh)

{

std::cout << "merging vertices " << v\_keep << " and " << v\_rm << std::endl;

for(halfedge\_descriptor h: [CGAL::halfedges\_around\_target](https://doc.cgal.org/latest/BGL/group__PkgBGLIterators.html#ga295060a50555471eab7f24addbb9bb49) (v\_rm, mesh))

set\_target(h, v\_keep, mesh); // to ensure that no halfedge points at the deleted vertex

remove\_vertex(v\_rm, mesh);

}

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/blobby.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh) || [CGAL::is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172) (mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

// Artificially create non-manifoldness for the sake of the example by merging some vertices

vertex\_descriptor v0 = \*(vertices(mesh).begin());

vertex\_descriptor v1 = \*(--(vertices(mesh).end()));

merge\_vertices(v0, v1, mesh);

// Count non manifold vertices

int counter = 0;

for(vertex\_descriptor v: vertices(mesh))

{

if([PMP::is\_non\_manifold\_vertex](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga121f588ac324938d9a6b6931a08661e1) (v, mesh))

{

std::cout << "vertex " << v << " is non-manifold" << std::endl;

++counter;

}

}

std::cout << counter << " non-manifold occurrence(s)" << std::endl;

// Fix manifoldness by splitting non-manifold vertices

std::vector<std::vector<vertex\_descriptor> > duplicated\_vertices;

std::size\_t new\_vertices\_nb = [PMP::duplicate\_non\_manifold\_vertices](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga25901cbedcc6123d7760ac5b9dc8d14e) (mesh,

NP::output\_iterator(

std::back\_inserter(duplicated\_vertices)));

std::cout << new\_vertices\_nb << " vertices have been added to fix mesh manifoldness" << std::endl;

for(std::size\_t i=0; i<duplicated\_vertices.size(); ++i)

{

std::cout << "Non-manifold vertex " << duplicated\_vertices\[i\].front() << " was fixed by creating";

for(std::size\_t j=1; j<duplicated\_vertices\[i\].size(); ++j)

std::cout << " " << duplicated\_vertices\[i\]\[j\];

std::cout << std::endl;

}

return EXIT\_SUCCESS;

}

[CGAL::Polygon\_mesh\_processing::is\_non\_manifold\_vertex](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga121f588ac324938d9a6b6931a08661e1)

bool is\_non\_manifold\_vertex(typename boost::graph\_traits< PolygonMesh >::vertex\_descriptor v, const PolygonMesh &pm)

returns whether a vertex of a polygon mesh is non-manifold.

**Definition:** manifoldness.h:52

[CGAL::Polygon\_mesh\_processing::duplicate\_non\_manifold\_vertices](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__combinatorial__repair__grp.html#ga25901cbedcc6123d7760ac5b9dc8d14e)

std::size\_t duplicate\_non\_manifold\_vertices(PolygonMesh &pm, const NamedParameters &np=parameters::default\_values())

duplicates all the non-manifold vertices of the input mesh.

**Definition:** manifoldness.h:428

[CGAL::is\_empty](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#gab6e6f18e6de73b9f85e38d0b56145172)

bool is\_empty(const FaceGraph &g)

[CGAL::halfedges\_around\_target](https://doc.cgal.org/latest/BGL/group__PkgBGLIterators.html#ga295060a50555471eab7f24addbb9bb49)

Iterator\_range< Halfedge\_around\_target\_iterator< Graph > > halfedges\_around\_target(typename boost::graph\_traits< Graph >::halfedge\_descriptor h, const Graph &g)

[CGAL::parameters](https://doc.cgal.org/latest/STL_Extension/namespaceCGAL_1_1parameters.html)

## Duplicated Vertices in Boundary Cycles

Similarly to the problematic configuration described in the previous section, another issue that can be present in a polygon mesh is the occurrence of a "pinched" hole, that is the configuration where, when starting from a border halfedge and walking the halfedges of this border, a geometric position appears more than once (although, with different vertices) before reaching the initial border halfedge again. The functions `CGAL::Polygon_mesh_processing::merge_duplicated_vertices_in_boundary_cycle()` and `CGAL::Polygon_mesh_processing::merge_duplicated_vertices_in_boundary_cycle()`, which merge vertices at identical positions, can be used to repair this configuration. During the operation, the boundary cycle is split into several boundary cycles, at each duplicated position.

## Geometric Repair

## Removal of Almost Degenerate Triangle Faces

Triangle faces of a mesh made up of almost collinear points are badly shaped elements that might not be desirable to have in a mesh. The function `CGAL::Polygon_mesh_processing::remove_almost_degenerate_faces()` enables removing such elements, with user-defined parameters to qualify what *almost* means (`cap_threshold` and `needle_threshold`). As some badly shaped elements are inevitable (the triangulation of a long cylinder with only vertices on the top and bottom circles for example), extra parameters can be passed to prevent the removal of such elements (`collapse_length_threshold` and `flip_triangle_height_threshold`).

## Self-intersection Resolution (Autorefinement) in Triangle Soups

Given a soup of triangles, a self-intersection is defined as the intersection of two triangles from the soup such that the intersection is not defined by the convex hull of one, two or three shared vertices. In other words, it is an intersection that happens in the interior of one of the two triangles, or in the interior of one of their edges, except if identical points are associated to different vertices of the triangle soup which would then also include overlaps of duplicated points.

The function `CGAL::Polygon_mesh_processing::autorefine_triangle_soup()` provides a way to refine a triangle soup using the intersections of the triangles from the soup. In particular, if some points are duplicated they will be merged. Note that if a kernel with exact predicates but inexact constructions is used, some new self-intersections might be introduced due to the rounding of the coordinates of intersection points. The `apply_iterative_snap_rounding` option can be used to resolve this issue. When set to `true`, it ensures that the coordinates are rounded to fit in `double` with potential additional subdivisions, preventing any self-intersections from occurring.

## Hole Filling

This package provides an algorithm for filling one closed hole that is either in a triangulated surface mesh or defined by a sequence of points that describe a polyline. The main steps of the algorithm are described in [\[2\]](https://doc.cgal.org/latest/PMP_Mesh_repair/citelist.html#CITEREF_liepa2003filling) and can be summarized as follows.

First, the largest patch triangulating the boundary of the hole is generated without introducing any new vertex. The patch is selected so as to minimize a quality function evaluated for all possible triangular patches. The quality function first minimizes the worst dihedral angle between patch triangles, then the total surface area of the patch as a tiebreaker. Following the suggestions in [\[3\]](https://doc.cgal.org/latest/PMP_Mesh_repair/citelist.html#CITEREF_zou2013algorithm), the performance of the algorithm is significantly improved by narrowing the search space to faces of a 3D Delaunay triangulation of the hole boundary vertices, from all possible patches, while searching for the best patch with respect to the aforementioned quality criteria.

For complex hole boundaries, the generated patch may have self-intersections. After hole filling, the patch can be refined and faired using the meshing functions `CGAL::Polygon_mesh_processing::refine()` and `CGAL::Polygon_mesh_processing::fair()` (see Section [Chapter\_PMPRemeshing](https://doc.cgal.org/latest/PMP_Remeshing/index.html#Chapter_PMPRemeshing)).

![](https://doc.cgal.org/latest/PMP_Mesh_repair/mech_hole_horz.jpg)

[Figure 79.1](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#fig__Mech_steps) Results of the main steps of the algorithm. From left to right: (a) the hole, (b) after triangulation, (c) after triangulation and refinement, (d) after triangulation, refinement, and fairing.

## API

This package provides four functions for hole filling:

- `CGAL::Polygon_mesh_processing::triangulate_hole_polyline()`: given a sequence of points defining the hole, triangulates the hole.
- `CGAL::Polygon_mesh_processing::triangulate_hole()`: given a border halfedge on the boundary of the hole on a mesh, triangulates the hole.
- `CGAL::Polygon_mesh_processing::triangulate_and_refine_hole()`: in addition to `CGAL::Polygon_mesh_processing::triangulate_hole()` the generated patch is refined.
- `CGAL::Polygon_mesh_processing::triangulate_refine_and_fair_hole()`: in addition to `CGAL::Polygon_mesh_processing::triangulate_and_refine_hole()` the generated patch is also faired.

## Examples

### Triangulate a Polyline

The following example triangulates a hole described by an input polyline.

**Example:** [PMP\_Mesh\_repair/triangulate\_polyline\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2triangulate_polyline_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Polygon\_mesh\_processing/triangulate\_hole.h>

#include <CGAL/utility.h>

#include \<vector>

#include \<iterator>

#include \<cassert>

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point;

int main()

{

std::vector\<Point> polyline;

polyline.push\_back(Point( 1.,0.,0.));

polyline.push\_back(Point( 0.,1.,0.));

polyline.push\_back(Point(-1.,0.,0.));

polyline.push\_back(Point( 1.,1.,0.));

// repeating first point (i.e. polyline.push\_back(Point(1.,0.,0.)) ) is optional

// any type, having Type(int, int, int) constructor available, can be used to hold output triangles

typedef [CGAL::Triple<int, int, int>](https://doc.cgal.org/latest/STL_Extension/classCGAL_1_1Triple.html) Triangle\_int;

std::vector<Triangle\_int> patch;

patch.reserve(polyline.size() -2); // there will be exactly n-2 triangles in the patch

[CGAL::Polygon\_mesh\_processing::triangulate\_hole\_polyline](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#gac1054e734715493e32e78d65fc1f0baf) (

polyline,

std::back\_inserter(patch));

for(std::size\_t i = 0; i < patch.size(); ++i)

{

std::cout << "Triangle " << i << ": "

<< patch\[i\].first << " " << patch\[i\].second << " " << patch\[i\].third

<< std::endl;

}

// note that no degenerate triangles are generated in the patch

std::vector\<Point> polyline\_collinear;

polyline\_collinear.push\_back(Point(1.,0.,0.));

polyline\_collinear.push\_back(Point(2.,0.,0.));

polyline\_collinear.push\_back(Point(3.,0.,0.));

polyline\_collinear.push\_back(Point(4.,0.,0.));

std::vector<Triangle\_int> patch\_will\_be\_empty;

[CGAL::Polygon\_mesh\_processing::triangulate\_hole\_polyline](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#gac1054e734715493e32e78d65fc1f0baf) (polyline\_collinear,

back\_inserter(patch\_will\_be\_empty));

assert(patch\_will\_be\_empty.empty());

return 0;

}

[CGAL::Triple](https://doc.cgal.org/latest/STL_Extension/classCGAL_1_1Triple.html)

[Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html)

[CGAL::Polygon\_mesh\_processing::triangulate\_hole\_polyline](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#gac1054e734715493e32e78d65fc1f0baf)

OutputIterator triangulate\_hole\_polyline(const PointRange1 &points, const PointRange2 &third\_points, OutputIterator out, const NamedParameters &np=parameters::default\_values())

creates triangles to fill the hole defined by points in the range points.

**Definition:** triangulate\_hole.h:724

[Kernel](https://doc.cgal.org/latest/Kernel_23/namespaceKernel.html)

### Hole Filling From the Border of the Hole

If the input polygon mesh contains one or more holes, they can be filled iteratively by detecting border edges (edges with only one incident non-null face) after each filling step.

Holes are filled sequentially, and the process stops when no border edge remains.

The example below illustrates this process, where holes are iteratively filled, refined, and faired. Optionally, only holes not exceeding a specified diameter or number of edges can be filled. This example assumes the mesh is stored in a `CGAL::Surface_mesh` data structure. Analogous examples for `CGAL::Polyhedron_3` and other classes are available in the code base.

**Example:** [PMP\_Mesh\_repair/hole\_filling\_example\_SM.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2hole_filling_example_SM_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/boost/graph/border.h>

#include <CGAL/Polygon\_mesh\_processing/triangulate\_hole.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <boost/lexical\_cast.hpp>

#include \<iostream>

#include \<iterator>

#include \<string>

#include \<tuple>

#include \<vector>

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point;

typedef [CGAL::Surface\_mesh\<Point>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef boost::graph\_traits\<Mesh>::halfedge\_descriptor halfedge\_descriptor;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace PMP = CGAL::Polygon\_mesh\_processing;

bool is\_small\_hole(halfedge\_descriptor h, Mesh & mesh,

double max\_hole\_diam, int max\_num\_hole\_edges)

{

int num\_hole\_edges = 0;

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html) hole\_bbox;

for (halfedge\_descriptor hc: [CGAL::halfedges\_around\_face](https://doc.cgal.org/latest/BGL/group__PkgBGLIterators.html#gaf157993cd9a52470eb96b12bcc0b67ab) (h, mesh))

{

const Point& p = mesh.point(target(hc, mesh));

hole\_bbox += p.bbox();

++num\_hole\_edges;

// Exit early, to avoid unnecessary traversal of large holes

if (num\_hole\_edges > max\_num\_hole\_edges) return false;

if (hole\_bbox.[xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c) () - hole\_bbox.[xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1) () > max\_hole\_diam) return false;

if (hole\_bbox.[ymax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a9d06f61bd89faa841e011ff53edf745f) () - hole\_bbox.[ymin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a2088e16a1f0a20e011e5b94c2e9c222a) () > max\_hole\_diam) return false;

if (hole\_bbox.[zmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a98def8b9515f31ded759d781969ddaf6) () - hole\_bbox.[zmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a6c55430abc7fda54571cf1075c7f2f8b) () > max\_hole\_diam) return false;

}

return true;

}

// Incrementally fill the holes that are no larger than given diameter

// and with no more than a given number of edges (if specified).

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/mech-holes-shark.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

// Both of these must be positive in order to be considered

double max\_hole\_diam = (argc > 2)? boost::lexical\_cast\<double>(argv\[2\]): -1.0;

int max\_num\_hole\_edges = (argc > 3)? boost::lexical\_cast\<int>(argv\[3\]): -1;

unsigned int nb\_holes = 0;

std::vector<halfedge\_descriptor> border\_cycles;

// collect one halfedge per boundary cycle

[CGAL::extract\_boundary\_cycles](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga28bba3efbd0352497f28c3c8185be09f) (mesh, std::back\_inserter(border\_cycles));

for(halfedge\_descriptor h: border\_cycles)

{

if(max\_hole\_diam > 0 && max\_num\_hole\_edges > 0 &&

!is\_small\_hole(h, mesh, max\_hole\_diam, max\_num\_hole\_edges))

continue;

std::vector<face\_descriptor> patch\_facets;

std::vector<vertex\_descriptor> patch\_vertices;

bool success = std::get<0>([PMP::triangulate\_refine\_and\_fair\_hole](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#ga18eac756a8f8e5d5f73e645fd4e26cad) (mesh, h,

CGAL::parameters::face\_output\_iterator(std::back\_inserter(patch\_facets))

.vertex\_output\_iterator(std::back\_inserter(patch\_vertices))));

std::cout << "\* Number of facets in constructed patch: " << patch\_facets.size() << std::endl;

std::cout << " Number of vertices in constructed patch: " << patch\_vertices.size() << std::endl;

std::cout << " Is fairing successful: " << success << std::endl;

++nb\_holes;

}

std::cout << std::endl;

std::cout << nb\_holes << " holes have been filled" << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) ("filled\_SM.off", mesh, CGAL::parameters::stream\_precision(17));

std::cout << "Mesh written to: filled\_SM.off" << std::endl;

return 0;

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

[CGAL::Polygon\_mesh\_processing::triangulate\_refine\_and\_fair\_hole](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#ga18eac756a8f8e5d5f73e645fd4e26cad)

auto triangulate\_refine\_and\_fair\_hole(PolygonMesh &pmesh, typename boost::graph\_traits< PolygonMesh >::halfedge\_descriptor border\_halfedge, const NamedParameters &np=parameters::default\_values())

triangulates, refines and fairs a hole in a polygon mesh.

**Definition:** triangulate\_hole.h:562

[CGAL::extract\_boundary\_cycles](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga28bba3efbd0352497f28c3c8185be09f)

OutputIterator extract\_boundary\_cycles(const Graph &g, OutputIterator out)

[CGAL::halfedges\_around\_face](https://doc.cgal.org/latest/BGL/group__PkgBGLIterators.html#gaf157993cd9a52470eb96b12bcc0b67ab)

Iterator\_range< Halfedge\_around\_face\_iterator< Graph > > halfedges\_around\_face(typename boost::graph\_traits< Graph >::halfedge\_descriptor h, const Graph &g)

![](https://doc.cgal.org/latest/PMP_Mesh_repair/fork.jpg)

[Figure 79.2](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#fig__Triangulated_fork) Holes in the fork model are filled with triangle patches.

An additional parameter, `visitor`, can be used to track the algorithm's phases, enabling users to implement timeouts or monitor progress.

**Example:** [PMP\_Mesh\_repair/hole\_filling\_visitor\_example.cpp](https://doc.cgal.org/latest/PMP_Mesh_repair/PMP_Mesh_repair_2hole_filling_visitor_example_8cpp-example.html)

Show / Hide

#include <CGAL/Exact\_predicates\_inexact\_constructions\_kernel.h>

#include <CGAL/Surface\_mesh.h>

#include <CGAL/boost/graph/border.h>

#include <CGAL/Polygon\_mesh\_processing/triangulate\_hole.h>

#include <CGAL/Polygon\_mesh\_processing/IO/polygon\_mesh\_io.h>

#include <CGAL/Real\_timer.h>

#include <boost/lexical\_cast.hpp>

#include \<iostream>

#include \<iterator>

#include \<string>

#include \<tuple>

#include \<vector>

#include \<stdexcept>

typedef CGAL::Real\_timer Timer;

typedef [Kernel::Point\_3](https://doc.cgal.org/latest/Kernel_23/classKernel_1_1Point__3.html) Point;

typedef [CGAL::Surface\_mesh\<Point>](https://doc.cgal.org/latest/Surface_mesh/classCGAL_1_1Surface__mesh.html) Mesh;

typedef boost::graph\_traits\<Mesh>::vertex\_descriptor vertex\_descriptor;

typedef boost::graph\_traits\<Mesh>::halfedge\_descriptor halfedge\_descriptor;

typedef boost::graph\_traits\<Mesh>::face\_descriptor face\_descriptor;

namespace PMP = CGAL::Polygon\_mesh\_processing;

bool is\_small\_hole(halfedge\_descriptor h, Mesh & mesh,

double max\_hole\_diam, int max\_num\_hole\_edges)

{

int num\_hole\_edges = 0;

[CGAL::Bbox\_3](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html) hole\_bbox;

for (halfedge\_descriptor hc: [CGAL::halfedges\_around\_face](https://doc.cgal.org/latest/BGL/group__PkgBGLIterators.html#gaf157993cd9a52470eb96b12bcc0b67ab) (h, mesh))

{

const Point& p = mesh.point(target(hc, mesh));

hole\_bbox += p.bbox();

++num\_hole\_edges;

// Exit early, to avoid unnecessary traversal of large holes

if (num\_hole\_edges > max\_num\_hole\_edges) return false;

if (hole\_bbox.[xmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a3f5e323700e1509624a02d151237cc4c) () - hole\_bbox.[xmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#aab574470a2591f187553ca1166e682e1) () > max\_hole\_diam) return false;

if (hole\_bbox.[ymax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a9d06f61bd89faa841e011ff53edf745f) () - hole\_bbox.[ymin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a2088e16a1f0a20e011e5b94c2e9c222a) () > max\_hole\_diam) return false;

if (hole\_bbox.[zmax](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a98def8b9515f31ded759d781969ddaf6) () - hole\_bbox.[zmin](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Bbox__3.html#a6c55430abc7fda54571cf1075c7f2f8b) () > max\_hole\_diam) return false;

}

return true;

}

struct Stop: std::exception

{

Stop()

{}

};

struct Progress:

public PMP::Hole\_filling::Default\_visitor

{

Progress(double time\_limit)

: time\_limit(time\_limit)

{}

Progress(const Progress&) = delete;

void start\_planar\_phase() const

{

std::cout << "Start planar phase"<< std::endl;

}

void end\_planar\_phase(bool success) const

{

std::cout << "End planar phase " << (success? "(success)": "(failed)") << std::endl;

}

void start\_quadratic\_phase(std::size\_t n)

{

timer.start();

quadratic\_i = 0;

quadratic\_n = n;

quadratic\_report = n / 10;

std::cout << "Start quadratic phase with estimated " << n << " steps" << std::endl;

}

void quadratic\_step()

{

if (quadratic\_i++ == quadratic\_report) {

std::cout << double(quadratic\_i) / double(quadratic\_n) \* 100 << "%" << std::endl;

quadratic\_report += quadratic\_n / 10;

}

}

void end\_quadratic\_phase(bool success) const

{

timer.stop();

std::cout << "End quadratic phase " << timer.time() << " sec. " << (success? "(success)": "(failed)") << std::endl;

timer.reset();

}

void start\_cubic\_phase(std::size\_t n)

{

timer.start();

cubic\_n = n;

cubic\_report = n / 10;

std::cout << "Start cubic phase with " << n << " steps" << std::endl;

}

void cubic\_step()

{

if (timer.time() > time\_limit) {

std::cout << "Let's stop here" << std::endl;

throw Stop();

}

if (cubic\_i++ == cubic\_report) {

std::cout << double(cubic\_i) / double(cubic\_n) \* 100 << "%" << std::endl;

cubic\_report += cubic\_n / 10;

}

}

void end\_cubic\_phase() const

{

std::cout << "End cubic phase " << timer.time() << " sec. " << std::endl;

}

mutable Timer timer;

double time\_limit;

std::size\_t quadratic\_n = 0, quadratic\_i = 0, quadratic\_report = 0;

std::size\_t cubic\_n = 0, cubic\_i = 0, cubic\_report = 0;

};

// Incrementally fill the holes that are no larger than given diameter

// and with no more than a given number of edges (if specified).

int main(int argc, char\* argv\[\])

{

const std::string filename = (argc > 1)? argv\[1\]: CGAL::data\_file\_path("meshes/mech-holes-shark.off");

Mesh mesh;

if(!PMP::IO::read\_polygon\_mesh(filename, mesh))

{

std::cerr << "Invalid input." << std::endl;

return 1;

}

// Both of these must be positive in order to be considered

double max\_hole\_diam = (argc > 2)? boost::lexical\_cast\<double>(argv\[2\]): -1.0;

int max\_num\_hole\_edges = (argc > 3)? boost::lexical\_cast\<int>(argv\[3\]): -1;

unsigned int nb\_holes = 0;

std::vector<halfedge\_descriptor> border\_cycles;

// collect one halfedge per boundary cycle

[CGAL::extract\_boundary\_cycles](https://doc.cgal.org/latest/BGL/group__PkgBGLHelperFct.html#ga28bba3efbd0352497f28c3c8185be09f) (mesh, std::back\_inserter(border\_cycles));

for(halfedge\_descriptor h: border\_cycles)

{

if(max\_hole\_diam > 0 && max\_num\_hole\_edges > 0 &&

!is\_small\_hole(h, mesh, max\_hole\_diam, max\_num\_hole\_edges))

continue;

Progress progress(10.0);

bool success = false;

try {

success = std::get<0>([PMP::triangulate\_refine\_and\_fair\_hole](https://doc.cgal.org/latest/PMP_Mesh_repair/group__PMP__hole__filling__grp.html#ga18eac756a8f8e5d5f73e645fd4e26cad) (mesh, h,

CGAL::parameters::visitor(std::ref(progress)).use\_delaunay\_triangulation(true)));

}

catch (const Stop&) {

std::cout << "We stopped with a timeout" << std::endl;

}

std::cout << " Is fairing successful: " << success << std::endl;

++nb\_holes;

}

std::cout << std::endl;

std::cout << nb\_holes << " holes have been filled" << std::endl;

[CGAL::IO::write\_polygon\_mesh](https://doc.cgal.org/latest/BGL/group__PkgBGLIOFct.html#gafa143949a33371dc6df8307be1ab8a66) ("filled\_SM.off", mesh, CGAL::parameters::stream\_precision(17));

std::cout << "Mesh written to: filled\_SM.off" << std::endl;

return 0;

}

## Performance

The hole filling algorithm has a complexity which depends on the number of vertices. While [\[2\]](https://doc.cgal.org/latest/PMP_Mesh_repair/citelist.html#CITEREF_liepa2003filling) has a running time of $O(n^3)$, [\[3\]](https://doc.cgal.org/latest/PMP_Mesh_repair/citelist.html#CITEREF_zou2013algorithm) in most cases has running time of $O(n \log n)$. We benchmarked the function `triangulate_refine_and_fair_hole()` for the two meshes below (as well as two more meshes with smaller holes). The machine used was a PC running Windows 10 with an Intel Core i7 CPU clocked at 2.70 GHz. The program was compiled with the Visual C++ 2013 compiler with the O2 option, which maximizes speed.

![](https://doc.cgal.org/latest/PMP_Mesh_repair/elephants-with-holes.png)

[Figure 79.3](https://doc.cgal.org/latest/PMP_Mesh_repair/index.html#fig__Elephants) The elephant on the left/right has a hole with 963/7657 vertices.

The following running times were observed:

| \# vertices | without Delaunay (sec.) | with Delaunay (sec.) |
| --- | --- | --- |
| 565 | 8.5 | 0.03 |
| 774 | 21 | 0.035 |
| 967 | 43 | 0.06 |
| 7657 | na | 0.4 |

## Implementation History

Functionalities related to mesh and polygon soup repair have been introduced steadily over multiple versions since CGAL 4.10, in joint work between Sébastien Loriot and Mael Rouxel-Labbé.