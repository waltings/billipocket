"""
Performance and load testing for critical paths.

Tests cover:
- Database query performance with large datasets
- Invoice calculation performance with many lines
- PDF generation performance under load
- Memory usage patterns
- Response time benchmarks for critical operations
- Pagination performance
- Search and filtering performance
- Bulk operations performance
"""

import pytest
import time
import psutil
import os
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from typing import List

from app.models import db, Client, Invoice, InvoiceLine, VatRate
from app.services.numbering import generate_invoice_number
from app.services.totals import calculate_invoice_totals
from tests.fixtures.test_data_factory import TestDataFactory


# Performance test markers
pytestmark = pytest.mark.performance


class TestDatabasePerformance:
    """Test database performance with large datasets."""
    
    @pytest.fixture(autouse=True)
    def setup_performance_data(self, db_session):
        """Setup large dataset for performance testing."""
        self.factory = TestDataFactory(db_session)
        
        # Create VAT rates
        VatRate.create_default_rates()
        
        # Create test data
        self.clients = [self.factory.create_client() for _ in range(50)]
        self.invoices = []
        
        # Create invoices with varying complexity
        for i in range(200):
            client = self.clients[i % len(self.clients)]
            line_count = 1 + (i % 10)  # 1-10 lines per invoice
            invoice = self.factory.create_complete_invoice(
                client=client,
                line_count=line_count
            )
            self.invoices.append(invoice)
    
    def test_client_query_performance(self, db_session):
        """Test client query performance."""
        start_time = time.time()
        
        # Query all clients
        clients = Client.query.all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert len(clients) >= 50
        assert query_time < 1.0, f"Client query took {query_time:.3f}s (should be < 1s)"
    
    def test_invoice_query_performance(self, db_session):
        """Test invoice query performance with joins."""
        start_time = time.time()
        
        # Query invoices with client data (join)
        invoices = Invoice.query.join(Client).all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert len(invoices) >= 200
        assert query_time < 2.0, f"Invoice query with join took {query_time:.3f}s (should be < 2s)"
    
    def test_invoice_lines_query_performance(self, db_session):
        """Test querying invoices with all their lines."""
        start_time = time.time()
        
        # Query invoices with all lines loaded
        invoices = Invoice.query.options(db.joinedload(Invoice.lines)).all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert len(invoices) >= 200
        assert query_time < 3.0, f"Invoice + lines query took {query_time:.3f}s (should be < 3s)"
        
        # Verify lines are loaded
        total_lines = sum(len(inv.lines) for inv in invoices)
        assert total_lines > 200  # Should have many lines
    
    def test_filtering_performance(self, db_session):
        """Test filtering performance on large dataset."""
        start_time = time.time()
        
        # Complex filter query
        recent_invoices = Invoice.query.join(Client).filter(
            Invoice.date >= date.today() - timedelta(days=30),
            Invoice.status.in_(['saadetud', 'makstud']),
            Client.name.ilike('%OÜ%')
        ).all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert query_time < 1.5, f"Complex filtering took {query_time:.3f}s (should be < 1.5s)"
    
    def test_pagination_performance(self, db_session):
        """Test pagination performance."""
        page_size = 20
        
        start_time = time.time()
        
        # Test first page
        page1 = Invoice.query.paginate(page=1, per_page=page_size, error_out=False)
        
        # Test middle page
        page5 = Invoice.query.paginate(page=5, per_page=page_size, error_out=False)
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert len(page1.items) <= page_size
        assert len(page5.items) <= page_size
        assert query_time < 1.0, f"Pagination queries took {query_time:.3f}s (should be < 1s)"
    
    def test_search_performance(self, db_session):
        """Test search performance with LIKE queries."""
        start_time = time.time()
        
        # Search across multiple fields
        search_term = "Test"
        results = Invoice.query.join(Client).filter(
            db.or_(
                Invoice.number.ilike(f'%{search_term}%'),
                Client.name.ilike(f'%{search_term}%'),
                Client.email.ilike(f'%{search_term}%')
            )
        ).all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        assert query_time < 2.0, f"Search query took {query_time:.3f}s (should be < 2s)"


class TestCalculationPerformance:
    """Test performance of invoice calculations."""
    
    def test_single_invoice_calculation_performance(self, db_session):
        """Test calculation performance for single invoice with many lines."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        client = factory.create_client()
        invoice = factory.create_invoice(client=client)
        
        # Create 100 lines
        for i in range(100):
            factory.create_invoice_line(
                invoice=invoice,
                qty=Decimal(str(1 + (i % 10))),
                unit_price=Decimal(str(50 + (i * 2.5)))
            )
        
        db_session.commit()
        
        start_time = time.time()
        
        # Calculate totals
        calculate_invoice_totals(invoice)
        
        end_time = time.time()
        calc_time = end_time - start_time
        
        assert calc_time < 0.1, f"Calculation for 100 lines took {calc_time:.3f}s (should be < 0.1s)"
        assert invoice.subtotal > 0
        assert invoice.total > invoice.subtotal
    
    def test_bulk_calculation_performance(self, db_session):
        """Test bulk calculation performance."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        # Create 50 invoices with lines
        invoices = []
        for _ in range(50):
            client = factory.create_client()
            invoice = factory.create_complete_invoice(client=client, line_count=5)
            invoices.append(invoice)
        
        start_time = time.time()
        
        # Recalculate all totals
        for invoice in invoices:
            calculate_invoice_totals(invoice)
        
        end_time = time.time()
        calc_time = end_time - start_time
        
        assert calc_time < 1.0, f"Bulk calculation for 50 invoices took {calc_time:.3f}s (should be < 1s)"
    
    def test_vat_calculation_performance(self, db_session):
        """Test VAT calculation performance with various rates."""
        from app.services.totals import calculate_vat_amount
        
        amounts = [Decimal(str(i * 10.5)) for i in range(1000)]
        rates = [Decimal('24.00'), Decimal('20.00'), Decimal('9.00'), Decimal('0.00')]
        
        start_time = time.time()
        
        # Calculate VAT for 1000 amounts with different rates
        results = []
        for amount in amounts:
            for rate in rates:
                vat = calculate_vat_amount(amount, rate)
                results.append(vat)
        
        end_time = time.time()
        calc_time = end_time - start_time
        
        assert len(results) == 4000  # 1000 amounts * 4 rates
        assert calc_time < 0.5, f"VAT calculation for 4000 operations took {calc_time:.3f}s (should be < 0.5s)"


class TestMemoryUsage:
    """Test memory usage patterns."""
    
    def get_memory_usage(self):
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024  # Convert to MB
    
    def test_large_dataset_memory_usage(self, db_session):
        """Test memory usage when loading large datasets."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        initial_memory = self.get_memory_usage()
        
        # Create large dataset
        clients = [factory.create_client() for _ in range(100)]
        invoices = []
        
        for i in range(500):
            client = clients[i % len(clients)]
            invoice = factory.create_complete_invoice(client=client, line_count=3)
            invoices.append(invoice)
        
        peak_memory = self.get_memory_usage()
        memory_increase = peak_memory - initial_memory
        
        # Clean up
        del invoices
        del clients
        
        final_memory = self.get_memory_usage()
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB (should be < 100MB)"
        
        # Memory should be mostly freed after cleanup
        memory_freed = peak_memory - final_memory
        assert memory_freed > memory_increase * 0.5, "Memory was not properly freed"
    
    def test_query_memory_efficiency(self, db_session):
        """Test that queries don't load unnecessary data."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        # Create test data
        clients = [factory.create_client() for _ in range(50)]
        for client in clients:
            factory.create_complete_invoice(client=client, line_count=5)
        
        initial_memory = self.get_memory_usage()
        
        # Query only necessary fields
        invoice_numbers = db_session.query(Invoice.number).all()
        
        memory_after_light_query = self.get_memory_usage()
        
        # Load full objects
        full_invoices = Invoice.query.options(db.joinedload(Invoice.lines)).all()
        
        memory_after_full_query = self.get_memory_usage()
        
        light_query_increase = memory_after_light_query - initial_memory
        full_query_increase = memory_after_full_query - memory_after_light_query
        
        # Light query should use much less memory than full query
        assert full_query_increase > light_query_increase * 2, "Full query should use significantly more memory"
        
        assert len(invoice_numbers) >= 50
        assert len(full_invoices) >= 50


class TestBulkOperations:
    """Test performance of bulk operations."""
    
    def test_bulk_insert_performance(self, db_session):
        """Test bulk insert performance."""
        factory = TestDataFactory(db_session)
        
        start_time = time.time()
        
        # Bulk create clients
        clients = []
        for i in range(100):
            client = Client(
                name=f'Bulk Client {i}',
                email=f'bulk{i}@test.ee',
                phone=f'+372 555{i:04d}'
            )
            clients.append(client)
        
        # Bulk add to session
        db_session.add_all(clients)
        db_session.commit()
        
        end_time = time.time()
        insert_time = end_time - start_time
        
        assert insert_time < 2.0, f"Bulk insert of 100 clients took {insert_time:.3f}s (should be < 2s)"
        
        # Verify all were inserted
        count = Client.query.filter(Client.name.like('Bulk Client %')).count()
        assert count == 100
    
    def test_bulk_update_performance(self, db_session):
        """Test bulk update performance."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        # Create test invoices
        client = factory.create_client()
        invoices = []
        for i in range(100):
            invoice = factory.create_invoice(
                client=client,
                status='mustand'
            )
            invoices.append(invoice)
        
        db_session.commit()
        
        start_time = time.time()
        
        # Bulk update status
        db_session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'mustand'
        ).update({'status': 'saadetud'})
        
        db_session.commit()
        
        end_time = time.time()
        update_time = end_time - start_time
        
        assert update_time < 1.0, f"Bulk update of 100 invoices took {update_time:.3f}s (should be < 1s)"
        
        # Verify all were updated
        updated_count = Invoice.query.filter(
            Invoice.client_id == client.id,
            Invoice.status == 'saadetud'
        ).count()
        assert updated_count == 100
    
    def test_bulk_delete_performance(self, db_session):
        """Test bulk delete performance."""
        factory = TestDataFactory(db_session)
        
        # Create test clients
        clients = [factory.create_client() for _ in range(100)]
        db_session.commit()
        
        # Get their IDs
        client_ids = [c.id for c in clients]
        
        start_time = time.time()
        
        # Bulk delete
        db_session.query(Client).filter(Client.id.in_(client_ids)).delete(synchronize_session=False)
        db_session.commit()
        
        end_time = time.time()
        delete_time = end_time - start_time
        
        assert delete_time < 1.0, f"Bulk delete of 100 clients took {delete_time:.3f}s (should be < 1s)"
        
        # Verify all were deleted
        remaining_count = Client.query.filter(Client.id.in_(client_ids)).count()
        assert remaining_count == 0


class TestNumberingPerformance:
    """Test invoice numbering performance."""
    
    def test_invoice_number_generation_performance(self, db_session):
        """Test performance of invoice number generation."""
        factory = TestDataFactory(db_session)
        client = factory.create_client()
        
        # Create some existing invoices to make numbering more complex
        for i in range(10):
            factory.create_invoice(
                client=client,
                number=f'2025-{i:04d}'
            )
        
        db_session.commit()
        
        start_time = time.time()
        
        # Generate 100 invoice numbers
        numbers = []
        for _ in range(100):
            number = generate_invoice_number()
            numbers.append(number)
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        assert generation_time < 1.0, f"Generating 100 invoice numbers took {generation_time:.3f}s (should be < 1s)"
        
        # Verify uniqueness
        assert len(set(numbers)) == len(numbers), "Generated numbers should be unique"
    
    def test_number_availability_check_performance(self, db_session):
        """Test performance of number availability checking."""
        from app.services.numbering import is_invoice_number_available
        
        factory = TestDataFactory(db_session)
        client = factory.create_client()
        
        # Create invoices with various numbers
        existing_numbers = []
        for i in range(100):
            number = f'2025-{i:04d}'
            factory.create_invoice(client=client, number=number)
            existing_numbers.append(number)
        
        db_session.commit()
        
        start_time = time.time()
        
        # Check availability of 200 numbers (100 existing, 100 new)
        test_numbers = existing_numbers + [f'2026-{i:04d}' for i in range(100)]
        
        results = []
        for number in test_numbers:
            available = is_invoice_number_available(number)
            results.append(available)
        
        end_time = time.time()
        check_time = end_time - start_time
        
        assert check_time < 2.0, f"Checking 200 number availability took {check_time:.3f}s (should be < 2s)"
        
        # Verify results
        existing_available = sum(results[:100])  # First 100 should not be available
        new_available = sum(results[100:])       # Last 100 should be available
        
        assert existing_available == 0, "Existing numbers should not be available"
        assert new_available == 100, "New numbers should be available"


class TestReportingPerformance:
    """Test performance of reporting and aggregation queries."""
    
    def test_revenue_calculation_performance(self, db_session):
        """Test performance of revenue calculations."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        # Create clients and invoices
        clients = [factory.create_client() for _ in range(20)]
        
        for client in clients:
            # Create invoices with different statuses
            for status in ['mustand', 'saadetud', 'makstud']:
                for _ in range(5):
                    factory.create_complete_invoice(
                        client=client,
                        status=status,
                        line_count=3
                    )
        
        start_time = time.time()
        
        # Calculate total revenue (paid invoices only)
        total_revenue = db_session.query(
            db.func.sum(Invoice.total)
        ).filter(
            Invoice.status == 'makstud'
        ).scalar() or Decimal('0')
        
        # Calculate revenue by client
        client_revenue = db_session.query(
            Client.name,
            db.func.sum(Invoice.total)
        ).join(Invoice).filter(
            Invoice.status == 'makstud'
        ).group_by(Client.id, Client.name).all()
        
        # Calculate revenue by month
        monthly_revenue = db_session.query(
            db.func.date_trunc('month', Invoice.date),
            db.func.sum(Invoice.total)
        ).filter(
            Invoice.status == 'makstud'
        ).group_by(
            db.func.date_trunc('month', Invoice.date)
        ).all()
        
        end_time = time.time()
        report_time = end_time - start_time
        
        assert report_time < 2.0, f"Revenue reporting queries took {report_time:.3f}s (should be < 2s)"
        
        # Verify results
        assert total_revenue > 0
        assert len(client_revenue) > 0
        assert len(monthly_revenue) > 0
    
    def test_status_summary_performance(self, db_session):
        """Test performance of invoice status summaries."""
        factory = TestDataFactory(db_session)
        VatRate.create_default_rates()
        
        # Create test data
        client = factory.create_client()
        statuses = ['mustand', 'saadetud', 'makstud', 'tähtaeg ületatud']
        
        for status in statuses:
            for _ in range(25):  # 25 invoices per status
                factory.create_complete_invoice(
                    client=client,
                    status=status,
                    line_count=2
                )
        
        start_time = time.time()
        
        # Status summary query
        status_summary = db_session.query(
            Invoice.status,
            db.func.count(Invoice.id).label('count'),
            db.func.sum(Invoice.total).label('total_amount')
        ).group_by(Invoice.status).all()
        
        # Overdue invoices count
        overdue_count = Invoice.query.filter(
            Invoice.due_date < date.today(),
            Invoice.status == 'saadetud'
        ).count()
        
        end_time = time.time()
        summary_time = end_time - start_time
        
        assert summary_time < 1.0, f"Status summary queries took {summary_time:.3f}s (should be < 1s)"
        
        # Verify results
        assert len(status_summary) == 4  # 4 different statuses
        for status, count, total in status_summary:
            assert count == 25
            assert total > 0


# Performance test configuration
class TestConfiguration:
    """Test configuration for performance benchmarks."""
    
    # Performance thresholds (in seconds)
    QUERY_THRESHOLD = 1.0
    CALCULATION_THRESHOLD = 0.1
    BULK_OPERATION_THRESHOLD = 2.0
    MEMORY_LIMIT_MB = 100
    
    @classmethod
    def validate_performance(cls, operation_time: float, threshold: float, operation_name: str):
        """Validate that operation meets performance requirements."""
        if operation_time > threshold:
            pytest.fail(f"{operation_name} took {operation_time:.3f}s (threshold: {threshold}s)")
    
    @classmethod
    def log_performance(cls, operation_name: str, operation_time: float, record_count: int = None):
        """Log performance metrics for analysis."""
        rate = f" ({record_count/operation_time:.0f} records/sec)" if record_count else ""
        print(f"Performance: {operation_name} took {operation_time:.3f}s{rate}")


# Benchmarking utilities
@pytest.fixture
def benchmark_timer():
    """Timer fixture for benchmarking operations."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time
    
    return Timer()


@pytest.fixture
def memory_monitor():
    """Memory monitoring fixture."""
    class MemoryMonitor:
        def __init__(self):
            self.process = psutil.Process(os.getpid())
            self.initial_memory = None
        
        def start(self):
            self.initial_memory = self.process.memory_info().rss / 1024 / 1024
        
        def current(self):
            return self.process.memory_info().rss / 1024 / 1024
        
        def increase(self):
            if self.initial_memory is None:
                return None
            return self.current() - self.initial_memory
    
    return MemoryMonitor()