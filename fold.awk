BEGIN{ rp="Organism_227\"|Organism_26781\"|Organism_21610\"|Organism_52857\"|Organism_57584\"" }
skip==1 { if ($0 ~ /<\/rdf:Description>/) skip=0; next }
($0 ~ /<rdf:Description rdf:about=/) && ($0 ~ rp) { if ($0 !~ /<\/rdf:Description>/) skip=1; nb++; next }
($0 ~ /rdf:resource=/) && ($0 ~ rp) { nr++; next }
($0 ~ /<\/rdf:RDF>/) && (done!=1) { while((getline l < FRAG)>0) print l; done=1; print; next }
{ print }
END{ print "removed_blocks="nb" removed_refs="nr" injected="(done?"yes":"NO") > "/dev/stderr" }
