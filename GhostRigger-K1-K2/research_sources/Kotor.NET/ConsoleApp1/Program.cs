using ConsoleApp1;
using Kotor;
using Kotor.NET.Common.Geometry;
using Kotor.NET.Common.Item;
using Kotor.NET.Formats.KotorBWM;
using Kotor.NET.Resources.KotorUTP;
using Silk.NET.Input;
using Silk.NET.Maths;
using Silk.NET.OpenGLES;
using Silk.NET.Windowing;


//Viewer viewer = new();
//viewer.Run();

var utp = new UTP();
utp.Inventory.Add(new StoredItem { ResRef = "ABC" });
utp.Inventory.Add(new StoredItem { ResRef = "saber" });
new UTPDecompiler(utp).CompileGFF();



var bwm = new BWM();

var v1 = new Vector3(0, 0, 0);
var v2 = new Vector3(1, 0, 0);
var v3 = new Vector3(0, 1, 0);
var v4 = new Vector3(1, 1, 0);
var v5 = new Vector3(2, 0, 0);

bwm.Faces = new()
{
    new(default, null, null, new[] { v1, v2, v3 }),
    new(default, null, null, new[] { v2, v4, v3 }),
    new(default, null, null, new[] { v2, v5, v4 }),
};
//var a = bwm.CalculateAABBs();
var b = bwm.Faces[0].FindAdjacency(bwm.Faces[1]);

Console.WriteLine();
