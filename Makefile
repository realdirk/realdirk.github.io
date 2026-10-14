QUARTO = quarto

.PHONY: all website preview clean publish

# Default: build the website
all: website

# Render the website into docs/
website:
	$(QUARTO) render

# Preview locally with automatic reload
preview:
	$(QUARTO) preview

# Remove generated output and Quarto cache
clean:
	rm -rf docs _freeze .quarto

# Rebuild from scratch
rebuild: clean website

# Commit and publish to GitHub Pages
publish: website
	git add -A
	git commit -m "Update academic website"
	git push origin main