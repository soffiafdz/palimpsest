# Palimpsest Documentation

Welcome to the Palimpsest documentation. This guide will help you understand and use Palimpsest, a system for managing structured journal entries with YAML frontmatter and SQL database integration.

## Quick Navigation

### Getting Started
- [Getting Started Guide](getting-started.md) - New to Palimpsest? Start here!

### Reference Documentation
Complete references for quick lookup:
- [Command Reference](reference/commands.md) - All CLI commands (plm, metadb, validate, jsearch)
- [Metadata Field Reference](reference/metadata-field-reference.md) - Comprehensive YAML field documentation
- [Metadata Examples](reference/metadata-examples.md) - Example YAML frontmatter with all fields

### Integrations
Editor and tool integrations:
- [Neovim Integration](integrations/neovim.md) - Neovim plugin for browsing, searching, and validation

### Development Documentation
For contributors and developers:
- [Development Overview](development/README.md) - Start here for development
- [Architecture](development/architecture.md) - Modular architecture and design patterns
- [Database Managers](development/database-managers.md) - Entity manager patterns
- [Validators](development/validators.md) - Validation system architecture
- [Type Checking](development/type-checking.md) - Pyright configuration and patterns
- [Testing](development/testing.md) - Comprehensive testing guide
- [Neovim Plugin Development](development/neovim-plugin-dev.md) - Extending the Neovim integration

## Documentation Organization

This documentation is organized by topic and purpose:

- **Getting Started**: Introduction and onboarding for new users
- **Reference**: Complete field, command, and system references for quick lookup
- **Guides**: Task-oriented workflows and how-to guides
- **Integrations**: Editor and tool integrations
- **Development**: Architecture, patterns, and contributor information

## Target Audiences

- **New Users**: Start with [Getting Started](getting-started.md), then explore [Reference](reference/) and [Guides](guides/)
- **Power Users**: Dive into [Reference](reference/) for quick lookups and [Guides](guides/) for workflows
- **Developers**: Check out [Development](development/) documentation (but you can reference main docs too)

## Need Help?

If you can't find what you're looking for:
1. Check the [Command Reference](reference/commands.md) for CLI usage
2. Check the [Metadata Field Reference](reference/metadata-field-reference.md) for YAML fields
3. Check the [Troubleshooting](#troubleshooting) sections in relevant guides

## Contributing to Documentation

Documentation should explain:
- **What**: What does this feature/component do?
- **Why**: Why does it exist? What problem does it solve?
- **How**: How do you use it?

Documentation should NOT contain:
- Historical proposals or implementation reports
- Change logs or update summaries (use git history for that)
