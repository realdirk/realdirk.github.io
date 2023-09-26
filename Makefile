QUARTO=quarto
FLAGS=render

all: clean website book

book: book/index.qmd
	$(QUARTO) $(FLAGS) book --to html

website: 
	$(QUARTO) $(FLAGS)
	touch book/index.qmd

clean: 
	rm -rf docs \_freeze

