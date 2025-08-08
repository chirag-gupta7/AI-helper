# Dependency Installation Guide

## Basic Installation

To install the core AI-helper dependencies:

```bash
cd backend
pip install -r requirements.txt
```

## exa-py Integration (Optional)

This project is now compatible with `exa-py` for enhanced search capabilities. 

### Option 1: Install exa-py separately
```bash
pip install exa-py==1.14.20
```

### Option 2: Use the optional requirements file
```bash
pip install -r requirements.txt -r requirements_exa.txt
```

## Dependency Compatibility

The requirements have been updated to resolve conflicts with exa-py 1.14.20:

- **requests**: Updated from `==2.31.0` to `>=2.32.3`
- **httpx**: Added `>=0.28.1` (new requirement)
- **gevent**: Updated from `==22.10.2` to `==23.9.1` (fixed build issues)

These changes ensure:
- ✅ No dependency conflicts when installing exa-py
- ✅ Backward compatibility with existing functionality  
- ✅ Resolved gevent build issues on newer Python versions

## Alternative Requirements Files

- `requirements.txt` - Main requirements with exa-py compatibility
- `requirements_fixed.txt` - Alternative fixed versions
- `compatible_requirements.txt` - Minimal compatible versions
- `requirements_exa.txt` - Optional exa-py integration

## Troubleshooting

If you encounter any installation issues:

1. Make sure you're using a fresh virtual environment
2. Upgrade pip: `pip install --upgrade pip`
3. For build issues, install build tools: `pip install wheel setuptools`