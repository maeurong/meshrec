## Computer Science > Graphics

## Title:Fast Tetrahedral Meshing in the Wild

Authors:[Yixin Hu](https://arxiv.org/search/cs?searchtype=author&query=Hu,+Y), [Teseo Schneider](https://arxiv.org/search/cs?searchtype=author&query=Schneider,+T), [Bolun Wang](https://arxiv.org/search/cs?searchtype=author&query=Wang,+B), [Denis Zorin](https://arxiv.org/search/cs?searchtype=author&query=Zorin,+D), [Daniele Panozzo](https://arxiv.org/search/cs?searchtype=author&query=Panozzo,+D)

[View PDF](https://arxiv.org/pdf/1908.03581) [HTML (experimental)](https://arxiv.org/html/1908.03581v2)

> Abstract:We propose a new tetrahedral meshing method, fTetWild, to convert triangle soups into high-quality tetrahedral meshes. Our method builds on the TetWild algorithm, replacing the rational triangle insertion with a new incremental approach to construct and optimize the output mesh, interleaving triangle insertion and mesh optimization. Our approach makes it possible to maintain a valid floating-point tetrahedral mesh at all algorithmic stages, eliminating the need for costly constructions with rational numbers used by TetWild, while maintaining full robustness and similar output quality. This allows us to improve on TetWild in two ways. First, our algorithm is significantly faster, with running time comparable to less robust Delaunay-based tetrahedralization algorithms. Second, our algorithm is guaranteed to produce a valid tetrahedral mesh with floating-point vertex coordinates, while TetWild produces a valid mesh with rational coordinates which is not guaranteed to be valid after floating-point conversion. As a trade-off, our algorithm no longer guarantees that all input triangles are present in the output mesh, but in practice, as confirmed by our tests on the Thingi10k dataset, the algorithm always succeeds in inserting all input triangles.

| Subjects: | Graphics (cs.GR) |
| --- | --- |
| Cite as: | [arXiv:1908.03581](https://arxiv.org/abs/1908.03581) \[cs.GR\] |
|  | (or [arXiv:1908.03581v2](https://arxiv.org/abs/1908.03581v2) \[cs.GR\] for this version) |
|  | [https://doi.org/10.48550/arXiv.1908.03581](https://doi.org/10.48550/arXiv.1908.03581) |
| Journal reference: | ACM Trans. Graph. 39, 4, Article 117 (August 2020), 18 pages |
| Related DOI: | [https://doi.org/10.1145/3386569.3392385](https://doi.org/10.1145/3386569.3392385) |

## Submission history

From: Yixin Hu \[[view email](https://arxiv.org/show-email/391c27bc/1908.03581)\]  
**[\[v1\]](https://arxiv.org/abs/1908.03581v1)** Fri, 9 Aug 2019 18:00:15 UTC (39,996 KB)  
**\[v2\]** Fri, 24 Jan 2020 22:09:21 UTC (72,576 KB)

[Which authors of this paper are endorsers?](https://arxiv.org/auth/show-endorsers/1908.03581) | Disable MathJax ([What is MathJax?](https://info.arxiv.org/help/mathjax.html))