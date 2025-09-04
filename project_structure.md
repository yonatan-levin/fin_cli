# Project Restructuring Plan

## Current Structure
```
fundainsight/
├── app/
│   ├── picker.py
│   ├── main.py
│   ├── fincli.py
│   └── cli.py
└── calculators/
    ├── equity_calc.py
    └── filters.py
```

## New Clean Architecture Structure
```
fundainsight/
├── domain/                   # Core business logic and entities
│   ├── models/               # Domain entities
│   │   ├── __init__.py
│   │   ├── stock.py          # Stock entity
│   │   └── financial_data.py # Financial data entity
│   ├── exceptions/           # Custom domain exceptions
│   │   ├── __init__.py
│   │   └── financial_exceptions.py
│   └── interfaces/           # Abstract interfaces (ABCs)
│       ├── __init__.py
│       └── data_provider.py  # Interface for data providers
├── data/                     # Data access layer
│   ├── providers/            # Implementation of data providers 
│   │   ├── __init__.py
│   │   ├── yahoo_finance.py  # Yahoo Finance implementation
│   │   └── cache_provider.py # Caching implementation
│   └── repositories/         # Repository pattern implementations
│       ├── __init__.py
│       └── stock_repository.py
├── application/              # Application services and use cases
│   ├── __init__.py
│   ├── services/             # Application services
│   │   ├── __init__.py
│   │   ├── stock_service.py  # Stock-related services
│   │   └── analytics_service.py
│   └── use_cases/            # Use case implementations
│       ├── __init__.py
│       └── get_opportunities.py
├── presentation/             # User interfaces
│   ├── __init__.py
│   ├── cli/                  # CLI interface
│   │   ├── __init__.py
│   │   └── commands.py       # CLI commands
│   └── api/                  # API interface (future)
│       ├── __init__.py
│       └── routes.py
└── infrastructure/           # Infrastructure concerns
    ├── __init__.py
    ├── logging/              # Enhanced logging
    │   ├── __init__.py
    │   └── log_manager.py
    ├── config/               # Enhanced configuration
    │   ├── __init__.py
    │   └── settings.py
    └── utils/                # Utility functions
        ├── __init__.py
        └── circuit_breaker.py
```

## Implementation Steps

1. Create the new directory structure
2. Move existing code to appropriate locations, refactoring as needed
3. Create new interfaces and abstract classes for dependency injection
4. Implement the domain models and business logic
5. Add new infrastructure components (logging, config, etc.)
6. Update the CLI interface to use the new architecture
7. Update the main application entry point 