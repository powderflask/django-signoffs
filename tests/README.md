# Tests for Django Signoffs

---

### Unit Tests

All of the unit tests for Django Signoffs can be found in the signoffs.core.tests directory.


### Integration Tests

The integration tests for Django Signoffs require a test application (test_app) and can be found in the test_app.tests
directory.

> *The test_app application was designed to be used for testing only. To explore the features of Django Signoffs, take a 
> look at the demo application contained in the root directory.*

### Running Tests

To run the tests using your local Python interpreter, just run `pytest` in the root directory:

```shell
$ pytest
```

To run the tests across multiple Python versions, use `tox` instead:

```shell
$ tox
```

Good luck and happy testing! :-)