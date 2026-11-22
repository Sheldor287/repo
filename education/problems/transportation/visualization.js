const width = 1200;
const height = 700;

const svg = d3.select("#network");

d3.json("solution.json").then(data => {

    console.log("Loaded solution:", data);

    // Display objective
    d3.select("#objective")
        .text(`Optimal Transportation Cost: ${data.objective.toFixed(2)}`);

    // --------------------------------------------------
    // Positions
    // --------------------------------------------------

    const plantX = 200;
    const warehouseX = 1000;

    const plantSpacing =
        height / (data.plants.length + 1);

    const warehouseSpacing =
        height / (data.warehouses.length + 1);

    const positions = {};

    data.plants.forEach((plant, i) => {
        positions[plant.id] = {
            x: plantX,
            y: plantSpacing * (i + 1)
        };
    });

    data.warehouses.forEach((warehouse, i) => {
        positions[warehouse.id] = {
            x: warehouseX,
            y: warehouseSpacing * (i + 1)
        };
    });

    // --------------------------------------------------
    // Routes
    // --------------------------------------------------

    const maxFlow = d3.max(data.edges, d => d.flow);

    svg.selectAll(".route")
        .data(data.edges)
        .enter()
        .append("line")
        .attr("class", d =>
            d.flow > 0 ? "route route-used" : "route"
        )
        .attr("x1", d => positions[d.source].x)
        .attr("y1", d => positions[d.source].y)
        .attr("x2", d => positions[d.target].x)
        .attr("y2", d => positions[d.target].y)
        .attr("stroke-width", d =>
            d.flow > 0
                ? 1 + 8 * (d.flow / maxFlow)
                : 1
        )
        .attr("opacity", d =>
            d.flow > 0 ? 0.8 : 0.2
        );

    // --------------------------------------------------
    // Plants
    // --------------------------------------------------

    const plantNodes = svg.selectAll(".plant")
        .data(data.plants)
        .enter()
        .append("circle")
        .attr("class", "plant")
        .attr("cx", d => positions[d.id].x)
        .attr("cy", d => positions[d.id].y)
        .attr("r", 30);

    // --------------------------------------------------
    // Warehouses
    // --------------------------------------------------

    const warehouseNodes = svg.selectAll(".warehouse")
        .data(data.warehouses)
        .enter()
        .append("circle")
        .attr("class", "warehouse")
        .attr("cx", d => positions[d.id].x)
        .attr("cy", d => positions[d.id].y)
        .attr("r", 30);

    // --------------------------------------------------
    // Labels
    // --------------------------------------------------

    svg.selectAll(".plant-label")
        .data(data.plants)
        .enter()
        .append("text")
        .attr("class", "plant-label")
        .attr("x", d => positions[d.id].x)
        .attr("y", d => positions[d.id].y - 40)
        .attr("text-anchor", "middle")
        .text(d => `${d.id} (${d.capacity})`);

    svg.selectAll(".warehouse-label")
        .data(data.warehouses)
        .enter()
        .append("text")
        .attr("class", "warehouse-label")
        .attr("x", d => positions[d.id].x)
        .attr("y", d => positions[d.id].y - 40)
        .attr("text-anchor", "middle")
        .text(d => `${d.id} (${d.demand})`);

    // --------------------------------------------------
    // Edge labels
    // --------------------------------------------------

    svg.selectAll(".edge-label")
        .data(data.edges.filter(d => d.flow > 0))
        .enter()
        .append("text")
        .attr("class", "edge-label")
        .attr("x", d =>
            (positions[d.source].x + positions[d.target].x) / 2
        )
        .attr("y", d =>
            (positions[d.source].y + positions[d.target].y) / 2
        )
        .attr("text-anchor", "middle")
        .text(d => `${d.flow} for $${d.cost} each`);

});