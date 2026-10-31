---
title: How to cite the software, the methods and the data
description: How to cite exostab, the methods behind its indicators and the NASA Exoplanet Archive.
---

# Citing exostab

If exostab helps your work, please cite three things: the software, the methods behind the indicators you
report, and the data. If you use the stability catalog, see
[How to cite the catalog](https://mimitoz62.github.io/exostab/catalog/#how-to-cite-the-catalog).

## The software

The repository's [`CITATION.cff`](https://github.com/mimitoz62/exostab/blob/main/CITATION.cff) holds the
citation metadata; GitHub's **Cite this repository** button turns it into APA or BibTeX. In BibTeX:

```bibtex
@software{oz_exostab,
  author  = {{\"O}z, Mehmet},
  title   = {exostab: honest, traceable orbital-stability indicators for known exoplanet systems},
  year    = {2026},
  version = {1.0.1},
  doi     = {10.5281/zenodo.23844658},
  url     = {https://github.com/mimitoz62/exostab}
}
```

The DOI [10.5281/zenodo.23844658](https://doi.org/10.5281/zenodo.23844658) always resolves to the latest version, and
[Zenodo](https://zenodo.org/records/23844659) gives each version its own. Please also give the version you used; every `report.json` records it
(`software.exostab`).

## The methods

Cite the methods that the result you report relies on. Every `report.json` lists, for each indicator, the BibTeX
keys of the methods it used, and the full entries, with DOIs, are in
[`docs/references.bib`](https://github.com/mimitoz62/exostab/blob/main/docs/references.bib).

| If you report | Please cite | Keys in `references.bib` |
|---|---|---|
| Hill spacing | Gladman (1993), Marchal & Bozis (1982), Veras & Armitage (2004), Giuppone et al. (2013) and Petit, Laskar & Boué (2018); for three or more planets also Chambers et al. (1996) and Pu & Wu (2015, with the erratum of 2016) | `gladman1993`, `marchal1982`, `veras2004`, `giuppone2013`, `petit2018`, `chambers1996`, `pu2015`, `pu2015erratum` |
| Angular momentum deficit | Laskar & Petit (2017); Petit, Laskar & Boué (2017, 2018) | `laskar2017`, `petit2017`, `petit2018` |
| N-body integration and MEGNO | REBOUND (Rein & Liu 2012) with WHFast (Rein & Tamayo 2015) and IAS15 (Rein & Spiegel 2015); MEGNO (Cincotta & Simó 2000; Cincotta, Giordano & Simó 2003) from REBOUND's variational equations (Rein & Tamayo 2016); Wisdom (2015); Hadden & Lithwick (2018) | `rein2012`, `rein2015whfast`, `rein2015ias15`, `rein2016`, `cincotta2000`, `cincotta2003`, `wisdom2015`, `hadden2018` |
| SPOCK (optional) | Tamayo et al. (2020) | `tamayo2020` |

[Methods](methods.md) explains what each indicator computes and how the references are used.

## The data

> This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
> Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
> Exploration Program.

The archive also asks users to cite Christiansen et al. (2025) and, for the Planetary Systems Composite
Parameters table, [doi:10.26133/NEA13](https://doi.org/10.26133/NEA13) with the access date. The access date of
every run is stored in its `report.json` (`data.retrieved_utc`), together with the publication behind every
value. See [Data and assumptions](data-assumptions.md).

## Related work

exostab grew out of the Research Note *N-body Stability Constraints on the Two Giant Planets of the Red Giant
HD 127195* (Öz 2026, prepared for Research Notes of the AAS) and its code,
[mimitoz62/hd127195-stability](https://github.com/mimitoz62/hd127195-stability). The
[validation](validation.md) compares exostab with its results.
