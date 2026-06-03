# Montgomery County Area Civic Association Map

A public map and open boundary dataset for civic, neighborhood, and community
associations in and near Montgomery County, Maryland.

## Why this exists

Residents often do not know which civic or neighborhood association covers their
home.

That creates extra work for residents, association volunteers, and neighboring
groups with overlapping or hard-to-find boundary descriptions.

This project is meant to make the answer easier to find and easier to keep
accurate.

## View the current map

The latest published map is available on the GitHub Releases page:

[View the latest map release](https://github.com/cbetti/civic-map-builder/releases/latest)

Each release may include PNG map images and downloadable boundary data.

## Add or correct a boundary

You do not need to know GitHub, Python, GIS, or GeoJSON to contribute.

The most useful thing is accurate source information: an association name, a
website, bylaws, a map image, a PDF, a list of streets, notes about uncertainty,
or boundary data from a mapping tool.

GeoJSON copied from geojson.io, a shapefile, KML, or other GIS data is welcome,
but it is not required.

Approximate or descriptive boundaries are still useful if you say where the
information came from and what parts are uncertain.

Technical contributors can also submit a pull request. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## What belongs in the dataset

This project is for civic, neighborhood, community, and similar local
associations in and near Montgomery County, Maryland.

The dataset is most useful when each boundary includes the association's public
name, a public or verifiable source, boundary geometry, and notes about
uncertainty or overlap.

## Reusing the data

The boundary data is intended to be reusable by associations, residents,
researchers, civic groups, local websites, and other mapping projects.

Geospatial data in the `associations/` directory is dedicated to the public
domain under CC0 1.0. You may use, copy, modify, and redistribute it without
legal restrictions.

Credit is appreciated because it helps other groups find the project and
contribute improvements.

The software tools in this repository are licensed separately under the MIT
License.

## For developers and maintainers

This repository also contains a Python command-line tool for validating
association boundary files and rendering map assets.

Developer setup, rendering, basemap, and release instructions live in:

- [Technical setup](docs/technical_setup.md)
- [Maintainer release process](docs/maintainer_release.md)
- [Contributing](CONTRIBUTING.md)
