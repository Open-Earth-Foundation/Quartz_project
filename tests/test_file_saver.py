import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
from pathlib import Path
import logging

from agents.utils.file_saver import save_scrape_to_file, sanitize_filename

# Configure logging for tests - good practice to see logs during test runs
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestFileSaver(unittest.TestCase):

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("test file:name?.txt"), "test_file_name_.txt")
        self.assertEqual(sanitize_filename("  leading_trailing_spaces  "), "leading_trailing_spaces")
        self.assertEqual(sanitize_filename(""), "sanitized_empty_filename")
        self.assertEqual(sanitize_filename("longfilename_" * 20), ("longfilename_" * 20)[:200])

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_scrape_to_file_success(self, mock_file: MagicMock, mock_mkdir: MagicMock):
        logger.info("Running test_save_scrape_to_file_success")
        country = "Testlandia"
        sector = "Energy/Electricity"
        run_id = "2023-01-01T12:00:00"
        filename = "http://example.com/data?page=1.html"
        data_content = "<html><body>Test Data</body></html>"

        sane_country = sanitize_filename(country)
        # Avoid backslashes inside f-string expressions in tests (CI on Py3.11 errors on this)
        sane_sector = sector.replace(' ', '_').replace('/', '_').replace('\\', '_')
        sane_run_id = run_id.replace(' ', '_').replace('/', '_').replace('\\', '_')
        sane_sector_run_id = sanitize_filename(f"{sane_sector}_{sane_run_id}")
        sane_filename = sanitize_filename(filename)
        
        expected_path = Path("data/scrape_results") / sane_country / sane_sector_run_id / sane_filename

        result_path_str = save_scrape_to_file(
            data=data_content,
            country_name=country,
            filename=filename,
            sector=sector,
            run_id=run_id
        )

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        # Check that the parent of the expected path was what mkdir was called with
        # Path.mkdir is called on the instance of the path, so `mock_mkdir.call_args[0][0]` would be the Path object itself.
        # We want to check that `expected_path.parent.mkdir` was called.
        # The mock_mkdir is on Path.mkdir, so its first arg is the Path object itself.
        # We need to assert that the call to mkdir was on `expected_path.parent`.
        # This is a bit tricky with how Path.mkdir is mocked.
        # Instead, we can check the path passed to open.
        
        mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
        mock_file().write.assert_called_once_with(data_content)
        
        self.assertIsNotNone(result_path_str)
        self.assertEqual(Path(result_path_str), expected_path)
        logger.info(f"Test test_save_scrape_to_file_success completed. Expected path: {expected_path}, Result path: {result_path_str}")

    @patch('pathlib.Path.mkdir', side_effect=OSError("Test OS Error"))
    @patch('builtins.open', new_callable=mock_open)
    def test_save_scrape_to_file_mkdir_os_error(self, mock_file: MagicMock, mock_mkdir: MagicMock):
        logger.info("Running test_save_scrape_to_file_mkdir_os_error")
        country = "ErrorCountry"
        sector = "ErrorSector"
        run_id = "error_run"
        filename = "error.html"
        data_content = "error data"

        result_path_str = save_scrape_to_file(
            data=data_content,
            country_name=country,
            filename=filename,
            sector=sector,
            run_id=run_id
        )

        mock_mkdir.assert_called_once()
        mock_file.assert_not_called()
        self.assertIsNone(result_path_str)
        logger.info("Test test_save_scrape_to_file_mkdir_os_error completed.")

    @patch('pathlib.Path.mkdir') # Mock mkdir to succeed
    @patch('builtins.open', mock_open(read_data="data")) # Mock open
    def test_save_scrape_to_file_write_exception(self, mock_mkdir_success: MagicMock):
        # In this test, builtins.open is already mocked by the decorator.
        # We need to make the write call within the mocked open fail.
        # The mock_open callable returns a MagicMock for the file handle.
        # We can make its write method raise an exception.
        
        # Re-patch open specifically for this test to control the file handle's write method
        with patch('builtins.open', new_callable=mock_open) as mock_file_specific:
            mock_file_specific.return_value.write.side_effect = IOError("Test Write Error")
            logger.info("Running test_save_scrape_to_file_write_exception")
            
            country = "WriteFailCountry"
            sector = "WriteFailSector"
            run_id = "write_fail_run"
            filename = "write_fail.html"
            data_content = "write fail data"

            result_path_str = save_scrape_to_file(
                data=data_content,
                country_name=country,
                filename=filename,
                sector=sector,
                run_id=run_id
            )

            mock_mkdir_success.assert_called_once() # mkdir should still be called
            mock_file_specific.assert_called_once() # open should be called
            mock_file_specific().write.assert_called_once_with(data_content) # write should be attempted
            self.assertIsNone(result_path_str) # Should return None on failure
            logger.info("Test test_save_scrape_to_file_write_exception completed.")


if __name__ == '__main__':
    unittest.main() 
