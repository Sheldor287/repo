# PostgreSQL Notes

## Categories and Applications
### Add-ons, tools, and utilities

#### ASP Bluefin for PostgreSQL:
Bluefin is a Table Access Method for PostgreSQL that stores data in a compressed, append-only format for efficient storage and fast analytical scans.
#### pgAgent:
pgAgent is a job scheduling agent for PostgreSQL, capable of running multi-step batch/shell and SQL tasks on complex schedules. pgAgent can be managed using pgAdmin.
#### pgBouncer:
pgBouncer is a lightweight connection pooler for PostgreSQL.

### Database Drivers
#### psqlIODBC:
The official PostgreSQL ODBC driver (64bit version). Packaged by EnterpriseDB.

### Database Server
#### PostgreSQL:
The PostgreSQL database server, with pgAdmin and StackBuilder.

### Enterprise Tools
#### Postgres Enterprise Manager Agent
This is the monitoring agent for Postgres Enterprise Manager, that runs on the servers you wish to monitor.

#### Postgres Enterprise Manager Server
This is the server for Postgres Enterprise Manager.

Postgres Enterprise Manager is an enterprise-wide management tool for database developers, DBAs and system administrators who are looking to efficiently  monitor, manage, and tune small to large scale Postgres deployments.

To learn more about Postgres Enterprise Manager and download the Installation Guide and Getting Started Guide, visit the Postgres Enterprise Manager home page at: www.enterprisedb.com/postgres-enterprise-manager.

This is a trial download.

#### Replication Server
EDB Replication Server v6.2 is certified for PostgreSQL and EPAS v14 and provides replication support for tables based on PostgreSQL declarative partitioning. Additionally it allows removal of tables from a subscribed Publication and includes assorted bug fixes.
## Spatial Extensions

### PostGIS

PostGIS 3.6.2 bundle includes PostGIS 3.6.2 w GDAL 3.9.2 (SQLite 3.30.1, OpenJPEG 2.4.0, Expat 2.4.8, FreeXL 1.0.6, Arrow 13.0.0)  , GEOS 3.14.1, Proj 8.2.1, pgRouting 4.0.1,  osm2pgrouting, ogr_fdw 1.1.7 spatial foreign data wrapper extension, and pgPointcloud 1.2.5, h3-pg 4.1.4, MobilityDb 1.3.0rc1, pgSphere 1.5.2.

https://postgis.net/2026/02/PostGIS-Patch-Releases/

PostGIS "spatially enables" the PostgreSQL server, allowing it to be used as a backend spatial database for geographic information systems (GIS). PostGIS follows the OpenGIS "Simple Features Specification for SQL" and has been certified as compliant with the "Types and Functions" profile. 

https://github.com/pgRouting/pgrouting/releases/tag/v4.0.1
pgRouting extensions PostGIS for building routing applications

https://github.com/pgRouting/osm2pgrouting
osm2pgRouting for loading OSM data into pgrouting

https://github.com/pramsey/pgsql-ogr-fdw
ogr_fdw allows you to query flat files, relational databases, and web services to name a few.  Spatial columns get transformed to PostGIS geometry columns.

https://github.com/pgpointcloud/pointcloud
pgPointcloud introduces specialty types for storing point cloud data loaded from LIDAR.

https://github.com/zachasme/h3-pg
Uber h3 api with conversion of h3 index to postgis geometries.

https://github.com/MobilityDB/MobilityDB
MobilityDb for managing spatial trajectories

https://github.com/postgrespro/pgsphere/releases/tag/1.5.2
pgSphere is a PostgreSQL extension for spherical geometry.#
#