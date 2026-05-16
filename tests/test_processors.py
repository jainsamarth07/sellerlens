"""Unit tests for the CSV parser and profit calculator."""

import json

import pytest

from backend.processors.csv_parser import parse_seller_file


class TestParseSeller:
    def test_parse_csv_basic(self):
        csv_data = (
            "Order ID,Product Name,Quantity,Selling Price,Cost Price,Shipping Fee,Commission,GST\n"
            "ORD001,Widget A,2,500,300,40,50,18\n"
            "ORD002,Widget B,1,1200,800,60,120,36\n"
        )
        rows = parse_seller_file(csv_data.encode(), "test.csv")
        assert len(rows) == 2
        assert rows[0]["order_id"] == "ORD001"
        assert rows[0]["selling_price"] == 500.0

    def test_parse_empty_file(self):
        csv_data = "Order ID,Product Name,Quantity\n"
        rows = parse_seller_file(csv_data.encode(), "empty.csv")
        assert rows == []

    def test_handles_missing_columns_gracefully(self):
        csv_data = "random_col,another_col\nfoo,bar\n"
        rows = parse_seller_file(csv_data.encode(), "odd.csv")
        assert len(rows) == 1
