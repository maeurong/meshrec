[![Previous](https://wias-berlin.de/software/tetgen/1.5/doc/manual/previous_motif.gif)](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual001.html) [![Next](https://wias-berlin.de/software/tetgen/1.5/doc/manual/next_motif.gif)](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual003.html)

---

## 1 Introduction

TetGen is a robust, fast, and easy-to-use software for generating tetrahedral meshes suitable in many applications.

For a set of 3d (weighted) points, TetGen generates the Delaunay and weighted Delaunay tetrahedralization as well as their duals, the Voronoi diagram and power diagram. For a 3d polyhedral domain, TetGen generates the constrained Delaunay tetrahedralization and an isotropic adaptive tetrahedral mesh of it. Domain boundaries (edges and faces) are respected and can be preserved in the resulting mesh. The shapes of resulting tetrahedra can be provably good for a large class of inputs. One of its main applications is to simulate physical phenomena by numerical methods, such as finite element and finite volume methods. A good quality mesh is essential to achieve high accuracy and efficiency of the simulations.

The algorithms of TetGen are Delaunay-based. They can preserve arbitrary complex geometry and topology. TetGen uses a constrained Delaunay refinement algorithm which guarantees termination and good mesh quality. The robustness of TetGen is enhanced by using advanced technologies developed in computational geometry. A technical paper describing the algorithms and technologies used in TetGen is available \[[24](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Si2013-WIAS-Preprint-1762)\].

TetGen is an outcome of a long-term research project supported by Weierstrass Institute for Applied Analysis and Stochastics (WIAS). It is continuously developed and improved.

TetGen is written in C++. It uses only C standard library. It is easy to compile and runs on all major 32-bit and 64-bit computer systems. The source code of TetGen is freely available at [http://www.tetgen.org](http://www.tetgen.org/). It is distributed under the the terms of the GNU Affero General Public License (AGPL) (v 3.0 or later) or a commercial license provided by WIAS.

The remainder of this section is to give a brief description of the triangulation and meshing problems considered in TetGen, and an overview of the implemented algorithms. For basic usage of TetGen, most of the information are not necessary to know, but Sections [1.2.1](#sec%3Aplcs) and [1.2.5](#sec%3Ameshqual) contain some necessary guidelines to create correct inputs and to generate quality tetrahedral meshes.

### 1.1 Triangulations of Point Sets

Triangulations are basic geometric structures. A triangulation of a set V of points is a simplicial complex S whose vertex set is a subset of or equal to V, and the underlying space of S is the convex hull of V. Given a point set, there are many triangulations of it. Among them, the Delaunay triangulation is of the most interested one. Its dual is the Voronoi diagram of the point set. Delaunay triangulations and Voronoi diagrams have many nice mathematical properties \[[1](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Aurenhammer91), [12](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Rajan94), [7](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Edelsbrunner01)\]. They are extensively used in many applications.

#### 1.1.1 Delaunay Triangulations, Voronoi Diagrams

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual001.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual002.png)  
> 
> Figure 1: The Delaunay triangulation (left) and its dual Voronoi diagram (right) of a 2d point set.
> 
> ---

Let V be a set of points in ℝ <sup>d</sup>, σ be a k-simplex (0 ≤ k ≤ d) whose vertices are in V. A circumsphere of σ is a sphere that passes through all vertices of σ. If k = d, σ has a unique circumsphere, otherwise, there are infinitely many circumspheres of σ. We say that σ is Delaunay if there exists a circumsphere of σ such that no vertex of V lies inside it.

A Delaunay triangulation D of V is a simplicial complex such that all simplices are Delaunay, and the underlying space of D is the convex hull of V \[[6](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Delaunay34)\]. Figure [1](#fig%3A2dt) left illustrates a 2d Delaunay triangulation. A 3d Delaunay triangulation is also called a Delaunay tetrahedralization.

A Delaunay triangulation of V is unique if V is in general position, i.e., no d+2 points in V lie on a common sphere. Otherwise, we say that V contains degeneracies, i.e., there are d+2 points in V lie on a common sphere. Degeneracies can be removed by applying an arbitrary small perturbation onto the coordinates of points in V.

The dual of the Delaunay triangulation is the Voronoi diagram defined on the same vertex set (see Figure [1](#fig%3A2dt) right). For any vertex p ∈ V, the Voronoi cell of p is the set of points with distance to p not greater than to any other vertex of V, i.e. it is the set cell(p) = { x ∈ ℝ <sup>d</sup>; ||x − p|| ≤ ||x − q||, ∀ q ∈ V }, where || · || stands for the Euclidean distance. The Voronoi diagram of V is a subdivision of ℝ <sup>d</sup> into Voronoi cells (some of which may be unbounded) and their faces \[[27](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Voronoi1908)\]. It is a d-dimensional polyhedral complex. If the point set V is in general position, there is a one-to-one correspondence between the k-simplices of the Delaunay triangulation and the (d−k)-polyhedra of the Voronoi diagram, where 0 ≤ k ≤ d. In ℝ <sup>3</sup>, the vertices of the Voronoi diagram are the circumcenters of the tetrahedra of the Delaunay tetrahedralization.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual003.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual004.png)
> 
> Figure 2: The relation between Delaunay triangulation in ℝ <sup>d</sup> and convex hull in ℝ <sup>d+1</sup> (here d = 2). Left: Some 2d points and their corresponding 3d lift points. Right: The Delaunay triangulation of a set of 2d points and the lower convex hull of its 3d lifted points.
> 
> ---

There is a nice relation between a Delaunay triangulation in ℝ <sup>d</sup> and a convex hull in ℝ <sup>d+1</sup>. For any point p = (p <sub>0</sub>, p <sub>1</sub>, ⋯, p <sub>d−1</sub>) ∈ ℝ <sup>d</sup>, define its lifted point p <sup>+</sup> = (p <sub>0</sub>, p <sub>1</sub>, ⋯, p <sub>d−1</sub>, p <sub>d</sub>) ∈ ℝ <sup>d + 1</sup>, where p <sub>d</sub> = p <sub>0</sub> <sup>2</sup> + ⋯ + p <sub>d−1</sub> <sup>2</sup>. For any point set V ⊂ ℝ <sup>d</sup>, define V <sup>+</sup> = {p <sup>+</sup>; p ∈ V} ⊂ ℝ <sup>d+1</sup> be the lifted point set of V. All points in V <sup>+</sup> lie on a paraboloid in ℝ <sup>d + 1</sup> (see Figure [2](#fig%3Aliftmap) left). The convex hull of V <sup>+</sup> is a (d + 1)-dimensional convex polytope P. A lower face of P is a face of P which is on the downside of P (visible by points in V). The Delaunay triangulation of V is the projection of the set of lower faces of P onto d dimensions. Figure [2](#fig%3Aliftmap) right illustrates the relationship when d = 2. A simplex σ is a Delaunay simplex if and only if there exists a hyperplane in ℝ <sup>d+1</sup> passing through the lifted vertices of σ such that no other lifted vertices in V <sup>+</sup> lies below of it. Similarly, the Voronoi diagram of V is the projection of the lower faces of a convex polytope Q ⊂ ℝ <sup>d+1</sup> such that P and Q are polar to each other \[[29](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Ziegler1995-book)\].

#### 1.1.2 Weighted Delaunay Triangulations, Power Diagrams

Weighted Delaunay triangulations are generalizations of Delaunay triangulations by replacing the Euclidean distance by “weighted distance”.

A weighted point, p′ = (p, p <sup>2</sup>) ∈ ℝ <sup>d</sup> × ℝ, can be interpreted as a sphere centered at p with radius p. The weighted distance between p′ and z′ is

| π <sub>p′, z′</sub> = | √ | \|\|p − z \|\| <sup>2</sup> − (p <sup>2</sup> + z <sup>2</sup>) | , |
| --- | --- | --- | --- |

see Figure [3](#fig%3Aorthospheres) left for an example. In particular, points in ℝ <sup>d</sup> can be considered weighted points with zero weight.

Two weighted points p′, z′ are orthogonal if their weighted distance is zero, i.e.,

||p − z || <sup>2</sup> = (p <sup>2</sup> + z <sup>2</sup>).

We say that two weighted points are farther than orthogonal when their weighted distance is positive, and closer than orthogonal when the distance becomes an imaginary number.

In general, d+1 points in ℝ <sup>d</sup> define a unique circumsphere passing through them. Similarly, d+1 weighted points in ℝ <sup>d</sup> define a unique common orthosphere. When all points have zero weights, their orthosphere is just their circumsphere. Figure [3](#fig%3Aorthospheres) (right) gives an example of the orthosphere of three weighted points in two dimensions.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.png)
> 
> Figure 3: Left: The weighted distance (left) of two weighted points (p, p <sup>2</sup>) and (z, z <sup>2</sup>). Right: The orthosphere of three weighted points. (Figures are taken from Damrong Guoy’s PhD thesis.)
> 
> ---

Let V′ ⊂ ℝ <sup>d</sup> × ℝ be a finite set of weighted points. We say a sphere is empty if all weighted points in V′ are farther than orthogonal of it. The weighted Delaunay triangulation of V′ is a simplicial complex D′ such that every simplex has an orthosphere which is empty, and the underlying space of D′ is the convex hull of V′. Obviously, if all the points have the same weight, the weighted Delaunay triangulation is the same as the usual Delaunay triangulation. Note that, a weighted Delaunay triangulation does not necessarily contain all points in V′.

The dual of a weighted Delaunay triangulation is a weighted Voronoi diagram, also called the power diagram \[[1](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Aurenhammer91), [9](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#EdelsbrunnerShah96)\] of the weighted point set V′. Power diagrams can be similarly defined as the Voronoi diagram by using the weighted distance instead of the Euclidean distance. If no d + 2 weighted points of V′ share a common orthosphere, i.e., it is in general position, then the simplices of the weighted Delaunay triangulation and the cells of the power diagram have a one-to-one correspondence. In ℝ <sup>3</sup>, the vertices of the power diagram are the orthocenters of the tetrahedra of the weighted Delaunay tetrahedralization.

A weighted Delaunay triangulation of V ⊂ ℝ <sup>d</sup> is also the projection of the set of lower faces of a convex polytope P ⊂ ℝ <sup>d+1</sup>. Any point in p = {p <sub>0</sub>,..., p <sub>d−1</sub> } ∈ V is lifted to a point p′ = {p <sub>0</sub>,..., p <sub>d−1</sub>, p <sub>d</sub> } ∈ ℝ <sup>d+1</sup>, where p <sub>d</sub> = p <sub>0</sub> <sup>2</sup> + ⋯ + p <sub>d−1</sub> <sup>2</sup> − p <sup>2</sup> (p is the weight of p). For p ≠ 0, p′ does not lie on a paraboloid in ℝ <sup>d+1</sup>, but is moved vertically downward by p <sup>2</sup>. A simplex belongs to the weighted Delaunay triangulation of V (i.e., it has an empty orthosphere) if and only if there exits a hyperplane passing through the lifted weighted points of these simplex and no lifted weighted point of V lie below the hyperplane.

Both weighted Delaunay triangulations and power diagrams are called regular subdivisions of point sets \[[29](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Ziegler1995-book)\]. Regular subdivisions have nice combinatorial structures. They are one of the important objects studied in higher-dimensional convex polytopes \[[29](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Ziegler1995-book), [5](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Loera2010-Triangbook)\].

#### 1.1.3 Algorithms

Algorithms for generating Delaunay (and weighted Delaunay) tetrahedralizations are well studied in computational geometry \[[7](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Edelsbrunner01)\]. TetGen implemented two algorithms, the Bowyer-Watson algorithm \[[3](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Bowyer81), [28](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Watson81)\] and the incremental flip algorithm \[[9](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#EdelsbrunnerShah96)\]. Both algorithms are incremental, i.e., insert points one after another. Both have the worst case runtime O(n <sup>2</sup>). In most of the practical applications, they are usually very fast. The expected running time of these algorithms is O(n logn) if the points are uniformly distributed in \[0,1\] <sup>3</sup>.

The speed of incremental algorithms is very much affected by the cost of point location. TetGen uses a spatial sorting scheme \[[2](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Boissonnat2009-incrmentDT)\] to improve the point location. The idea is to sort the points such that nearby points in space have nearby indices. The points are first randomly sorted in different groups, then points in each group are sorted along the Hilbert curve. Inserting points in this order, each point location can be done in nearly constant time.

TetGen uses Shewchuk’s exact geometric predicates \[[15](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk1997-predicates)\] for performing the Orient3D, InSphere, and Orient4D tests. These suffice to guarantee the numerical robustness of generating Delaunay and weighted Delaunay tetrahedralizations. A simplified symbolic perturbation scheme \[[8](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Edelsbrunner90sos)\] is used to remove the degeneracies.

### 1.2 Tetrahedral Meshes of 3d Spaces

A tetrahedral mesh is a 3d simplicial complex that is a discrete representation of a 3d continuous space (domain), both in its topology and geometry. Note that a Delaunay tetrahedralization is a tetrahedral mesh of the convex hull of its vertex set. In general, a geometric domain may not be convex and may have arbitrarily complex boundaries.

The input domain of TetGen is modeled by a [piecewise linear complex](#sec%3Aplcs) (Section [1.2.1](#sec%3Aplcs)). The focuses of TetGen are the representation of the geometry (the boundary) and the quality of the mesh. TetGen generates several types of tetrahedral meshes to achieve these goals. They are explained in the following subsections.

#### 1.2.1 Piecewise Linear Complexes (PLCs)

At first we need a model to represent a 3d domain such that it can be easily described and handled. A 3d piecewise linear complex (PLC) X is a set of cells, that satisfies the following properties:

- (1) The boundary of each cell in X is a union of cells in X.
- (2) If two distinct cells f, g ∈ X intersect, their intersection is a union of cells in X.

It is first introduced by Miller, et al. \[[11](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Miller96)\], see Figure [4](#fig%3Aplc) left for an example.

> ---
> 
> | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual007.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual008.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual009.png) |
> | --- | --- |
> | A 3d PLC | non-PLCs |
> 
> Figure 4: Left: A 3d piecewise linear complex. The left shaded area shows a facet, which is non-convex and has a hole in it. It has also edges and vertices floating in it. The right shaded area shows an interior facet separating two sub-domains. Right: Configurations which are not PLCs.
> 
> ---

The boundary of a 3d PLC is the set of cells whose dimensions are less than or equal to 2. A 0-dimensional cell is a vertex. In particular, we call a 1-dimensional cell (an edge) a segment, and a 2-dimensional cell a facet. Each facet of a PLC is a 2d PLC. It may contain holes, segments and vertices in its interior, see Figure [4](#fig%3Aplc) left for an example.

PLCs are flexible in describing 3d geometric features. For instance, they permit facets, segments and vertices to float in a domain, or segments and vertices to float in the facet. One purpose of these floating cells is to constrain how the PLC can be meshed, so that boundary conditions may be applied at those cells.

The definition of a PLC disallows illegal intersections of its cells, see Figure [4](#fig%3Aplc) right for examples. Two segments only can intersect at a common vertex that is also in X. Two facets of X may intersect only at a union of vertices and segments which are also in X.  
The underlying space of a PLC X, denoted | X|, is ∪ <sub>f ∈ X</sub> f, which is the domain to be triangulated. A tetrahedral mesh of X, is a 3d simplicial complex T such that (1) X and T have the same vertices, (2) every cell in X is a union of simplices in T, and (3) | T| = | X|.

Let T be a tetrahedral mesh of a 3d PLC X. The boundary of X is respected by the elements of T, i.e., each segment of X is represented by a union of edges in T, and each facet of X is represented a union of triangles in T. To distinguish those edges and triangles of T which are on segments and facets of X, we call them boundary edges and boundary faces.  
TetGen uses a simple boundary representation (a surface mesh) to represent a 3d PLC. It is explained in Section [5.1.1](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#sec%3Adesplc) and in the file formats [.poly](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_poly) and [.smesh](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_smesh) of TetGen. Figure [5](#fig%3Aplcs) shows two typical surface meshes of 3d PLCs. The following points are useful to know.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual011.png)
> 
> Figure 5: Examples of surface meshes of PLCs.
> 
> ---

- TetGen does not generate the surface mesh of the PLC. It must be given by the users as the input of TetGen.
- TetGen is able to modify the surface mesh by further subdividing them. This is necessary in order to conform to the constrained Delaunay property and improve the mesh quality. This is the default choice of the [\-p](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY) switch.
- TetGen will preserve the surface mesh (does not subdivide it) when the switch [\-Y](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY) is applied.
- If the input surface mesh contains self-intersections, TetGen will detect them and stop the meshing process automatically.
- If the input surface mesh contains holes, i.e., it is not watertight, TetGen will finish the meshing process, but it returns an empty 3d tetrahedral mesh unless the [\-c](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-c) switch (to keep the convex hull of the mesh) is used.

#### Limitation of PLCs.

A PLC only gives a piecewise linear approximation of a 3d domain. It does not take the curvature of the surfaces into account. When TetGen modifies the surface mesh, it only modifies the linear edges and facets. This is unfortunately a limitation of using PLC.

#### 1.2.2 Steiner Points

There are 3d polyhedra which may not be tetrahedralized with only its own vertices, two typical examples are shown in Figure [6](#fig%3Auntetpoly). Nevertheless, it is always possible to tetrahedralize a polyhedron if Steiner points (which are not vertices of the polyhedron) are allowed.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual012.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual013.png)
> 
> Figure 6: Polyhedra which can not be tetrahedralized without Steiner points. Left: The Schönhardt polyhedron \[[14](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Schonhardt1928)\]. Right: The Chazelle’s polyhedron \[[4](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Chazelle1984)\].
> 
> ---

A Steiner tetrahedralization of a PLC X is a tetrahedralization of X ∪ S, where S is a finite set of Steiner points (disjoint from the vertices of X). TetGen generates Steiner tetrahedralizations of PLCs. Two types of Steiner points are used in TetGen:

- The first type of Steiner points are used in creating an initial tetrahedralization of PLC. These Steiner points are mandatory in order to create a valid tetrahedralization.
- The second type of Steiner points are used in creating quality tetrahedral meshes of PLCs. These Steiner points are optional, while they may be necessary in order to improve the mesh quality or to conform the size of mesh elements.

In both cases, TetGen tries to generate the Steiner points efficiently and limit the number of Steiner points as small as possible. The optimal locations and the optimal number of Steiner points is still a topic of research.

#### 1.2.3 Boundary Conformity

A fundamental problem in mesh generation is how to enforce a set of constraints, such as edges and triangles, to be preserved or represented by a mesh. These constraints usually describe the special features in the domain boundaries, such as the boundary complex of a PLC, and they are required to be correctly represented in the generated meshes. It is generally referred to the boundary conformity or boundary recovery problem.

Boundary conformity in 2d is very easy. One can enforce any edge (which does not intersect any boundary) into a triangulation. Moreover, it does not need any Steiner point. However, it is very difficult in 3d since it is not always possible to enforce an edge or a triangle into a tetrahedralization without using Steiner points.

TetGen always respects the boundary of the domain. TetGen can generate different types of (Steiner) tetrahedralizations such that input segments and facets of a PLC are respected.

- A conforming Delaunay tetrahedralization. It is a subcomplex of a Delaunay tetrahedralization, i.e., every tetrahedron is a Delaunay tetrahedron. It may contain Steiner points. Some Steiner points may lie on the boundary of the PLC, i.e., the boundary triangulation of the PLC may be a refinement of the original one.
- A constrained Delaunay tetrahedralization (CDT). Each of its tetrahedron satisfies a constrained Delaunay criteria, and it has many properties similar to those of a Delaunay tetrahedralization. It is further explained in Section [1.2.4](#sec%3Acdt). A CDT may contain Steiner points. Moreover, most of the Steiner points lie on the segments of the PLC. Hence, the boundary triangulation of the PLC may be a refinement of the original one.
- A constrained tetrahedralization. It is a tetrahedralization which preserves the input surface mesh of the PLC. It may contain Steiner points, but they must lie in the interior of the PLC. This type of tetrahedralization may be neither Delaunay nor constrained Delaunay.

These different types of tetrahedralizations produced by TetGen may find use in different situations. For instances, conforming DTs are desired for applications which need the Delaunay property. While this type of tetrahedralization usually need a large number of Steiner points. CDTs require much less Steiner points. They are an alternative choice of conforming DTs when the applications can accept non-Delaunay elements. Constrained tetrahedralizations are useful in many engineering applications for which the input domain boundaries need to be preserved.

#### 1.2.4 Constrained Delaunay Tetrahedralizations

A constrained Delaunay tetrahedralization (CDT) is a variation of a Delaunay tetrahedralization that is constrained to respect the edges and facets of X. CDTs in the plane were introduced by Lee and Lin \[[10](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#LeeLin86)\]. Shewchuk \[[16](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk98-cdttheorem), [21](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk08-CDTj1)\] generalized them into three or higher dimensions.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual014.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual015.png)
> 
> Figure 7: Left: The tetrahedron abcd is constrained Delaunay. Right: The triangle abc is locally Delaunay.
> 
> ---

In the following, we give two equivalent definitions of constrained Delaunay tetrahedralizations.

The visibility between two vertices p, q ∈ | X| is called occluded if there is a facet f ∈ X such that p and q lie on opposite sides of the plane that includes f, and the line segment pq intersects this facet (see Figure [7](#fig%3Acdttet)). A tetrahedron t whose vertices are in X is constrained Delaunay if its circumsphere encloses no vertex of X, which is visible from any point in the relative interior of t (see Figure [7](#fig%3Acdttet) Left).

A tetrahedralization T is a constrained Delaunay tetrahedralization of X if it is a tetrahedralization of X and every tetrahedron of T is constrained Delaunay.

Let s be a triangle in a tetrahedralization T of X. s is said to be locally Delaunay if either it belongs to only one tetrahedron of T, or it is a face of exactly two tetrahedra t <sub>1</sub> and t <sub>2</sub> and it has a circumsphere which does not enclose any vertex of t <sub>1</sub> and t <sub>2</sub>. Equivalently, the circumsphere of t <sub>1</sub> encloses no vertex of t <sub>2</sub> and vice versa (see Figure [7](#fig%3Acdttet) Right). A tetrahedralization T of P is a CDT of P if every triangle in T not included in any facet of P is locally Delaunay.

The definitions of Delaunay tetrahedralization and constrained Delaunay tetrahedralization are almost the same except that, for the CDT, we free the requirement of being locally Delaunay for triangles in the facet. Hence CDTs retain many nice properties of those of Delaunay tetrahedralizations, see \[[21](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk08-CDTj1), [23](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Si08thesis)\]. Note that simplices (tetrahedra, triangles, and edges) in a CDT are not always Delaunay.

A CDT of an arbitrary PLC X may not exist \[[21](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk08-CDTj1)\]. Steiner points are necessary to ensure the existence of a CDT. A *Steiner CDT* of X is a CDT of X ∪ S, where S ⊂ | X| is a set of Steiner points.

Compared to conforming Delaunay tetrahedralizations, (Steiner) CDTs usually require much less Steiner points.

#### 1.2.5 Mesh Quality, Tetrahedron Shape Measures

There is no unique definition of the term “mesh quality". It depends on the intended application and the numerical methods employed, see, e.g. \[[19](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk02elem)\].

As a general guideline, elements with very small and large angles (and dihedral angels) should be avoided since they usually downgrade the accuracy and performance of numerical methods.

Figure [8](#fig%3Atetshape) shows six differently shaped tetrahedra. A tetrahedron shape measure is a continuous function which evaluates the shape of a tetrahedron by a real number. Various tetrahedron shape measures have been suggested, some of them are equivalent.

> ---
> 
> | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual016.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual017.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual018.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual019.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual020.png) | ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual021.png) |
> | --- | --- | --- | --- | --- | --- |
> | Regular | Needle | Spindle | Wedge | Cap | Sliver |
> 
> Figure 8: Tetrahedra of different shapes.
> 
> ---

The most general shape measure for a simplex is the aspect ratio. The aspect ratio, η(τ), of a tetrahedron τ is the ratio between the longest edge length l <sub>max</sub> and the shortest height h <sub>min</sub>, i.e., η(τ) = l <sub>max</sub> /h <sub>min</sub>. The aspect ratio measures the “roundness" of a tetrahedron in terms of a value between √2/√3 and +∞. A low aspect ratio implies a better shape. Other possible definitions of aspect ratio exist, such as the ratio between the circumradius and inradius. These definitions are equivalent in the sense that if a tetrahedralization is bounded w.r.t. one of the ratios then it is bounded w.r.t. all the others.

The tetrahedron shape measures used in TetGen are the face angles (angles between two edges) and dihedral angles (angles between two faces) as the shape measures of tetrahedra. They work well with the Delaunay refinement algorithm used in TetGen. Also, the combination of them achieve the same objective as the aspect ratio.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual022.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual023.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual024.png)
> 
> Figure 9: The radius-edge ratio (R/L) of tetrahedra. Most of the badly shaped tetrahedra will have a large radius-edge-ratio except slivers (Right).
> 
> ---

To bound the smallest face angle is equivalent to bound the radius-edge ratio of the tetrahedron. The radius-edge ratio, ρ(τ) of a tetrahedron τ is the ratio between the radius r of its circumscribed ball and the length d of its shortest edge, i.e.,

| ρ(τ) = | rd | ≥ | 12 sinθ <sub>min</sub> | , |
| --- | --- | --- | --- | --- |

where θ <sub>min</sub> is the smallest face angle of τ, see Figure [9](#fig%3Aradiusedgeratio). The radius-edge ratio ρ(τ) is at least √6/4 ≈ 0.612, achieved by the regular tetrahedron. Most of the badly shaped tetrahedra will have a big radius-edge ratio (e.g., > 2.0) except the sliver, which is a type of very flat tetrahedra having no small edges, but nearly zero volume. A sliver can have a minimal value √2/2 ≈ 0.707, hence the radius-edge ratio is not equivalent to aspect ratio (due to the slivers). Nevertheless, the radius-edge ratio is a useful shape measure. It can be shown that if a tetrahedral mesh has a radius-edge ratio bounded for all of its tetrahedra, then the point set of the mesh is well spaced, and each node of the mesh has bounded degree \[[11](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Miller96), [23](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Si08thesis)\].

Each of the six edges of a tetrahedron τ is surrounded by two faces. At a given edge, the dihedral angle between two faces is the angle between the intersection of these faces and a plane perpendicular to the edge. The dihedral angle in τ is between 0 <sup>∘</sup> and 180 <sup>∘</sup>. The minimum dihedral angle φ <sub>min</sub> (τ) of τ is a tetrahedron shape measure used by TetGen.

#### 1.2.6 Mesh Adaptation, Mesh Sizing Functions

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual025.png) ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual026.png)
> 
> Figure 10: An adaptive tetrahedral mesh (left) and the calculated numerical solution (right) of a heat conduction problem.
> 
> ---

The goal of adaptive mesh generation is to generate a mesh which achieves the desired mesh quality with a small number of mesh elements. In numerical methods, such a mesh gives a good balance between the solution time and the accuracy of the solution, see Figure [10](#fig%3Aheat) for an example.

The total number of mesh element is determined by the mesh element sizes, i.e., the diameters of the mesh elements. It is in general no possible to determine a proper mesh element size in advance. It depends on the actual applications and the numerical methods employed.

As a general guideline for adaptive mesh generation, TetGen uses a mesh sizing function. Let X be a 3d PLC. A mesh sizing function H: | X| → ℝ, is a function that maps each point p ∈ | X| to a positive value H(p) which specifies the desired mesh edge lengths at the point location p. Typically, the mesh sizing function can be the geometrical features of the input PLC, an error distribution function obtained from a previous numerical solution, or a user-specified function.

A mesh sizing function H is isotropic if the edge length does not vary with respect to the directions at p, otherwise, it is anisotropic. The current version of TetGen only supports isotropic mesh sizing functions. An ideal sizing function is C <sup>∞</sup>, ∀ p ∈ | X|. However, in most cases, H is approximated by a discrete function specified at some points in | X|. The size at other points in | X| is obtained by means of interpolation.

TetGen supports several ways of defining a sizing function. It can be defined automatically, explicitly on various sources of volumes, facets, line segments, and points, or through user-defined sizing functions.

- By default, TetGen uses the local feature size \[[13](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Ruppert95)\] of the PLC. It is a distance function on | X| based on its boundary information.
- One can apply a bound of maximum volume (the [\-a](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-a) switch) on every tetrahedra of the mesh. It is the same as defining a global constant sizing function. For a domain consisting of multiple sub-domains (materials), the volume bound can vary in each sub-domain, see the [.poly](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_poly) and [.smesh](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_smesh) file formats.
- One can apply a bound of maximum area on each facet, or apply a bound of maximum edge length on each boundary segment of the input PLC, see the [.var](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_var) file format.
- One can define a mesh sizing function directly on the input PLC. In this way, to each vertex of the PLC a value for the mesh sizing function is to be assigned, see the [.mtr](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_mtr) file format.
- One can use a background mesh to define a sizing function. The background mesh can be any tetrahedral mesh. Its underlying space must cover the input PLC. To each mesh node of the background tetrahedral mesh a value for the mesh sizing function is assigned, which contains the desired edge length at that location in the PLC.

All the above ways of defining sizing function can be used at the same time. TetGen will automatically choose the smallest mesh element size. In the last two ways, i.e., defining mesh element sizes on nodes, it is possible to set the size to zero at a node. In this case, the mesh element size at this location is ignored.

#### 1.2.7 Mesh Optimization

Mesh optimization is an essential way for further improving the mesh quality. Typically, it improves one or several objective functions on mesh quality, such as the aspect ratio, minimum or maximum dihedral angles, etc.

Mesh optimization is usually done by applying various local mesh operations which either change the node locations or change the mesh connections. The most frequently used operations are: node smoothing, edge/face swapping, edge contraction, and vertex insertion. These operations are combined according to a schedule to iteratively improve the mesh quality. One can decide to either optimize the whole mesh (global optimization) or only optimize a part of the mesh (local optimization).

TetGen uses mesh optimization after the mesh generation. It locally optimizes the tetrahedral mesh to restore the Delaunay property and to improve the mesh quality. The current version uses the maximum dihedral angle as objective function. It provides options to choose local operations and to restrict the maximum number of iterations in the optimization procedure, see the [\-O](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-O) switch.

#### 1.2.8 Algorithms

Algorithms for constructing 3d CDTs were first considered by Shewchuk. In \[[16](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk98-cdttheorem)\], a sufficient condition for the existence of a CDT of a PLC (or a polyhedron) is given. Based on this condition, several algorithms for constructing Steiner CDTs are proposed \[[18](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk02-cdt), [20](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk03-FlipCDT), [26](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#SiGaertner05cdt), [25](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#SG2011)\]. TetGen’s CDT algorithm is from Si and Gärtner \[[26](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#SiGaertner05cdt), [25](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#SG2011)\].

The basic algorithm for generating quality tetrahedral meshes is the Delaunay refinement algorithm from Ruppert \[[13](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Ruppert95)\] and Shewchuk \[[17](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Shewchuk98refine)\]. This algorithm generates a quality mesh of Delaunay tetrahedra with no tetrahedra having a radius-edge ratio greater than 2.0 (equivalently, no face angle less than 14.5 <sup>o</sup>). The sizes of tetrahedra are graded from small to large over a short distance. TetGen implemented this algorithm for improving the mesh quality of a CDT of a PLC. In practice, the algorithm generates meshes generally surpassing the theoretical bounds and eliminates tetrahedra with small or large dihedral angles efficiently.

There are two theoretical problems of the basic Delaunay refinement algorithm. First, it does not remove slivers due to the use of radius-edge ratio as the sole tetrahedral shape measure. Second, it may not terminate if the input PLC X contains sharp features, i.e., there are two edges of X meeting at an acute angle, or two facets of X meeting at an acute dihedral angle.

TetGen uses the minimal dihedral angle of tetrahedron as a second shape measure for the Delaunay refinement algorithm, hence slivers are found by this measure and are removed by the above mentioned Delaunay refinement iterations. Since TetGen works with CDTs, it can detect all the sharp features in the CDT in advance. Then it starts the Delaunay refinement process. Tetrahedra at the sharp features are never removed. The modified algorithm in TetGen always terminates. However some badly-shaped tetrahedra near the sharp features may survive.

TetGen accepts a user-defined mesh sizing function to control the mesh element size. If this is given, TetGen will generate an adaptive tetrahedral mesh according to the input mesh sizing function. It uses a constrained Delaunay refinement algorithm \[[22](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual010.html#Si08cdt)\].

### 1.3 Description of the Meshing Process

Figure [11](#fig%3Aflowchart) shows a graphic flowchart of the meshing process in TetGen.

> ---
> 
> ![](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual027.png)
> 
> Figure 11: The flowchart of the mesh generation process of TetGen.
> 
> ---

Here are the general steps of TetGen to create a (quality) tetrahedral mesh. Many of these steps can be skipped, depending on the command line switches.

- 1\. Initialize constants and parse the command line.
- 2\. Read the vertices from a ([.node](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_node)) file and either
	- \- create the corresponding Delaunay tetrahedralization (DT) (no [\-r](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-r)), or
		- \- read an existing tetrahedral mesh from ([.ele](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_ele), [.face](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_face), [.edge](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_edge)) files and reconstruct it ([\-r](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-r)).
- 3\. Read the boundary informations (segments and facets) from ([.poly](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_poly) or [.smesh](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_smesh), [.edge](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_edge)) files and triangulate them ([\-p](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY)).
- 4\. Read the background mesh from (.b.node,.b.ele,.b.mtr...) files (if it is provided) and interpolate the mesh element size from the background mesh to the current mesh ([\-m](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-m)).
- 5\. Insert the boundary segments and facets into the DT ([\-p](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY)) by either
	- constructing a constrained Delaunay tetrahedralization (CDT) in which the segments and facets may be split into smaller pieces (no [\-Y](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY)), or
		- recovering the segments and facets in a tetrahedralization which contains them ([\-Y](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-pY)).
- 6\. Read the holes (-p), regional attributes (-pA), and regional volume constraints (-pa), and either
	- \- remove the exterior tetrahedra (in the holes and concavities) (no [\-c](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-c)), or
		- \- mark the exterior tetrahedra ([\-c](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-c)),
	and spread the regional attributes and volume constraints.
- 7\. Coarsen the mesh ([\-R](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-R)) by removing vertices which are either marked or inconsistent according to a [mesh sizing function](#sec%3Ameshadapt) ([\-m](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-m)).
- 8\. Read the list of additional vertices from a (.a.node) file (if it is provided) and insert them into the current mesh ([\-i](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-i)).
- 9\. Enforce the constraints on minimum quality bound ([\-q](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-q)) and maximum, volume ([\-a](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-a)), and [mesh sizing function](#sec%3Ameshadapt) ([\-m](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-m)).
- 10\. Optimize the mesh with respect to the optimization scheme ([\-O](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-O)) based on specified quality measures (-o).
- 11\. Write the output files and print the statistics.
- 12\. Check the consistency of the mesh ([\-C](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html#cmd-C)).

---

[![Previous](https://wias-berlin.de/software/tetgen/1.5/doc/manual/previous_motif.gif)](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual001.html) [![Next](https://wias-berlin.de/software/tetgen/1.5/doc/manual/next_motif.gif)](https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual003.html)