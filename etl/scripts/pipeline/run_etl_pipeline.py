#!/usr/bin/env python3
"""
Main ETL Pipeline Orchestrator
Manages the complete data pipeline execution flow from schema creation to data ingestion.

This script provides a single entry point for running the entire ETL pipeline:
1. Schema creation
2. Materialized views creation (required for analytics)
3. Data ingestion
4. Materialized view refresh (automatic after ingestion)

Usage:
    python etl/scripts/pipeline/run_etl_pipeline.py [options]

Examples:
    # Full pipeline (schema + materialized views + ingestion)
    python etl/scripts/pipeline/run_etl_pipeline.py --full

    # Only ingest data (assumes schema and materialized views exist)
    python etl/scripts/pipeline/run_etl_pipeline.py --ingest-only

    # Dry run (test without committing)
    python etl/scripts/pipeline/run_etl_pipeline.py --full --dry-run
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# Setup paths BEFORE importing scripts modules
# Add etl directory to sys.path so we can import scripts.* (scripts is in etl/scripts/)
_script_dir = Path(__file__).parent.parent  # pipeline -> scripts
_etl_dir = _script_dir.parent  # scripts -> etl
_etl_dir_str = str(_etl_dir)
if _etl_dir_str not in sys.path:
    sys.path.insert(0, _etl_dir_str)

from scripts.core.paths import setup_script_paths, get_data_source_path
from scripts.database.db_connection import test_connection

# Ensure paths are set up (this is idempotent)
setup_script_paths()


class ETLPipeline:
    """Orchestrates the complete ETL pipeline execution."""
    
    def __init__(self, dry_run: bool = False, verbose: bool = True):
        self.dry_run = dry_run
        self.verbose = verbose
        self.steps_completed = []
        self.steps_failed = []
    
    def log(self, message: str, level: str = "INFO"):
        """Print log message if verbose mode is enabled."""
        if self.verbose:
            prefix = {
                "INFO": "ℹ",
                "SUCCESS": "✓",
                "ERROR": "✗",
                "WARNING": "⚠",
                "STEP": "→"
            }.get(level, "•")
            print(f"{prefix} {message}")
    
    def run_step(self, step_name: str, step_func) -> bool:
        """Run a pipeline step and track success/failure."""
        self.log(f"Starting: {step_name}", "STEP")
        try:
            result = step_func()
            if result:
                self.steps_completed.append(step_name)
                self.log(f"Completed: {step_name}", "SUCCESS")
                return True
            else:
                self.steps_failed.append(step_name)
                self.log(f"Failed: {step_name}", "ERROR")
                return False
        except Exception as e:
            self.steps_failed.append(step_name)
            self.log(f"Error in {step_name}: {e}", "ERROR")
            if self.verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def check_database_connection(self) -> bool:
        """Verify database connectivity."""
        self.log("Checking database connection...", "STEP")
        if test_connection():
            self.log("Database connection successful", "SUCCESS")
            return True
        else:
            self.log("Database connection failed. Please check DATABASE_URL in .env", "ERROR")
            return False
    
    def create_schema(self) -> bool:
        """Create the unified database schema."""
        from scripts.database.create_schema import create_schema
        return create_schema()
    
    def create_materialized_views(self) -> bool:
        """Create optional materialized views for performance."""
        from scripts.database.create_materialized_views import create_materialized_views
        return create_materialized_views()
    
    def ingest_data(
        self,
        toast_file: Optional[str] = None,
        doordash_file: Optional[str] = None,
        square_dir: Optional[str] = None,
        ingest_all: bool = False,
        skip_refresh: bool = False
    ) -> bool:
        """Ingest data from all or specified sources."""
        from scripts.pipeline.ingest_unified_data import main as ingest_main
        from scripts.database.db_connection import get_db_connection
        
        # Import the ingester class directly
        from scripts.pipeline.ingest_unified_data import UnifiedDataIngester
        
        # Determine data source paths
        if ingest_all:
            data_dir = get_data_source_path()
            toast_file = str(data_dir / 'toast_pos_export.json') if not toast_file else toast_file
            doordash_file = str(data_dir / 'doordash_orders.json') if not doordash_file else doordash_file
            square_dir = str(data_dir / 'square') if not square_dir else square_dir
        
        # Validate files exist
        if toast_file and not Path(toast_file).exists():
            self.log(f"Toast file not found: {toast_file}", "WARNING")
            toast_file = None
        
        if doordash_file and not Path(doordash_file).exists():
            self.log(f"DoorDash file not found: {doordash_file}", "WARNING")
            doordash_file = None
        
        if square_dir and not Path(square_dir).exists():
            self.log(f"Square directory not found: {square_dir}", "WARNING")
            square_dir = None
        
        if not any([toast_file, doordash_file, square_dir]):
            self.log("No valid data sources found. Skipping ingestion.", "WARNING")
            return True  # Not an error, just nothing to ingest
        
        # Run ingestion
        conn = get_db_connection()
        try:
            ingester = UnifiedDataIngester(conn)
            ingester.setup_reference_data()
            
            if toast_file:
                self.log(f"Ingesting Toast data from: {toast_file}")
                ingester.ingest_toast_data(toast_file)
            
            if doordash_file:
                self.log(f"Ingesting DoorDash data from: {doordash_file}")
                ingester.ingest_doordash_data(doordash_file)
            
            if square_dir:
                self.log(f"Ingesting Square data from: {square_dir}")
                ingester.ingest_square_data(square_dir)
            
            if not self.dry_run:
                conn.commit()
                self.log("Data ingestion completed and committed", "SUCCESS")
                
                # Refresh materialized views if requested
                if not skip_refresh:
                    # Ensure connection is clean before refresh
                    try:
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    self.refresh_materialized_views(conn)
            else:
                conn.rollback()
                self.log("Data ingestion (DRY RUN) - no changes committed", "WARNING")
            
            ingester.print_stats()
            return True
            
        except Exception as e:
            conn.rollback()
            self.log(f"Error during ingestion: {e}", "ERROR")
            raise
        finally:
            conn.close()
    
    def refresh_materialized_views(self, conn=None) -> bool:
        """Refresh materialized views after data ingestion."""
        try:
            from scripts.refresh.refresh_materialized_views_sync import refresh_views_smart
            
            if conn is None:
                from scripts.database.db_connection import get_db_connection
                conn = get_db_connection()
                close_conn = True
            else:
                close_conn = False
            
            try:
                self.log("Refreshing materialized views...")
                result = refresh_views_smart(conn)
                if result['success']:
                    self.log(
                        f"Materialized views refreshed: {len(result['views_refreshed'])} views in {result['duration_seconds']:.2f}s",
                        "SUCCESS"
                    )
                    return True
                else:
                    self.log(f"Materialized view refresh failed: {result.get('message', 'Unknown error')}", "WARNING")
                    return False
            finally:
                if close_conn:
                    conn.close()
        except ImportError:
            self.log("Materialized views not created yet. Skipping refresh.", "WARNING")
            return True  # Not an error
        except Exception as e:
            self.log(f"Error refreshing materialized views: {e}", "WARNING")
            return False  # Non-fatal warning
    
    def run_full_pipeline(
        self,
        skip_refresh: bool = False
    ) -> bool:
        """Run the complete ETL pipeline."""
        self.log("=" * 60)
        self.log("Starting Full ETL Pipeline", "STEP")
        self.log("=" * 60)
        
        # Step 1: Check database connection
        if not self.run_step("Database Connection Check", self.check_database_connection):
            return False
        
        # Step 2: Create schema
        if not self.run_step("Create Unified Schema", self.create_schema):
            return False
        
        # Step 3: Create materialized views (required for analytics)
        if not self.run_step("Create Materialized Views", self.create_materialized_views):
            self.log("Materialized views creation failed, but continuing with data ingestion...", "WARNING")
            self.log("Note: Analytics queries require materialized views to be created", "WARNING")
        
        # Step 4: Ingest data
        if not self.run_step("Data Ingestion", lambda: self.ingest_data(ingest_all=True, skip_refresh=skip_refresh)):
            return False
        
        # Pipeline summary
        self.log("=" * 60)
        self.log("ETL Pipeline Summary", "STEP")
        self.log("=" * 60)
        self.log(f"Completed steps: {len(self.steps_completed)}")
        for step in self.steps_completed:
            self.log(f"  ✓ {step}", "SUCCESS")
        
        if self.steps_failed:
            self.log(f"Failed steps: {len(self.steps_failed)}")
            for step in self.steps_failed:
                self.log(f"  ✗ {step}", "ERROR")
            return False
        
        self.log("=" * 60)
        self.log("ETL Pipeline Completed Successfully!", "SUCCESS")
        self.log("=" * 60)
        return True
    
    def run_ingestion_only(
        self,
        toast_file: Optional[str] = None,
        doordash_file: Optional[str] = None,
        square_dir: Optional[str] = None,
        ingest_all: bool = False,
        skip_refresh: bool = False
    ) -> bool:
        """Run only the data ingestion step (assumes schema exists)."""
        self.log("=" * 60)
        self.log("Starting Data Ingestion Only", "STEP")
        self.log("=" * 60)
        
        # Check database connection
        if not self.run_step("Database Connection Check", self.check_database_connection):
            return False
        
        # Ingest data
        if not self.run_step(
            "Data Ingestion",
            lambda: self.ingest_data(
                toast_file=toast_file,
                doordash_file=doordash_file,
                square_dir=square_dir,
                ingest_all=ingest_all,
                skip_refresh=skip_refresh
            )
        ):
            return False
        
        self.log("=" * 60)
        self.log("Data Ingestion Completed Successfully!", "SUCCESS")
        self.log("=" * 60)
        return True


def main():
    """Main entry point for ETL pipeline."""
    parser = argparse.ArgumentParser(
        description="ETL Pipeline Orchestrator - Run the complete data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (schema + ingestion)
  python etl/scripts/pipeline/run_etl_pipeline.py --full

  # Only ingest data (assumes schema exists)
  python etl/scripts/pipeline/run_etl_pipeline.py --ingest-only

  # Full pipeline (schema + materialized views + ingestion)
  python etl/scripts/pipeline/run_etl_pipeline.py --full

  # Dry run (test without committing)
  python etl/scripts/pipeline/run_etl_pipeline.py --full --dry-run

  # Ingest specific sources
  python etl/scripts/pipeline/run_etl_pipeline.py --ingest-only --toast data/sources/toast_pos_export.json
        """
    )
    
    # Main execution modes
    execution_group = parser.add_mutually_exclusive_group(required=True)
    execution_group.add_argument(
        '--full',
        action='store_true',
        help='Run full pipeline: schema creation + data ingestion'
    )
    execution_group.add_argument(
        '--ingest-only',
        action='store_true',
        help='Run only data ingestion (assumes schema exists)'
    )
    
    # Data source options
    parser.add_argument(
        '--toast',
        type=str,
        help='Path to Toast POS JSON file'
    )
    parser.add_argument(
        '--doordash',
        type=str,
        help='Path to DoorDash orders JSON file'
    )
    parser.add_argument(
        '--square-dir',
        type=str,
        help='Path to Square data directory'
    )
    
    
    # Options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test run without committing changes'
    )
    parser.add_argument(
        '--skip-refresh',
        action='store_true',
        help='Skip materialized view refresh after ingestion'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Reduce output verbosity'
    )
    
    args = parser.parse_args()
    
    # Create pipeline instance
    pipeline = ETLPipeline(dry_run=args.dry_run, verbose=not args.quiet)
    
    # Execute based on mode
    try:
        if args.full:
            success = pipeline.run_full_pipeline(
                skip_refresh=args.skip_refresh
            )
        elif args.ingest_only:
            # Determine if we should ingest all sources
            ingest_all = not any([args.toast, args.doordash, args.square_dir])
            success = pipeline.run_ingestion_only(
                toast_file=args.toast,
                doordash_file=args.doordash,
                square_dir=args.square_dir,
                ingest_all=ingest_all,
                skip_refresh=args.skip_refresh
            )
        
        sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

