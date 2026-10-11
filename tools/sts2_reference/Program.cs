// Reads card reference data from the player's own copy of Slay the Spire 2's
// compiled game code (sts2.dll) using .NET's metadata reader. Read-only: the
// assembly is parsed as data, never loaded or executed, and no code is
// decompiled or written out - only facts (card -> pool, rarity, type, cost).
//
//   dotnet run -- "<path to sts2.dll>" > cards_from_game.json
using System.Collections.Immutable;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text.Json;

var dllPath = args.Length > 0 ? args[0]
    : @"N:\SteamLibrary\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64\sts2.dll";
// Optional: --debug <CardClass> prints that card's constructor IL to stderr.
var debugClass = args.Length > 2 && args[1] == "--debug" ? args[2] : null;

using var fs = File.OpenRead(dllPath);
using var pe = new PEReader(fs);
var md = pe.GetMetadataReader();

string TypeName(EntityHandle h) => h.Kind switch
{
    HandleKind.TypeDefinition => md.GetString(md.GetTypeDefinition((TypeDefinitionHandle)h).Name),
    HandleKind.TypeReference => md.GetString(md.GetTypeReference((TypeReferenceHandle)h).Name),
    _ => "",
};
string TypeNs(TypeDefinition t) => md.GetString(t.Namespace);

// enum name lookup: enum type name -> (value -> member name)
var enums = new Dictionary<string, Dictionary<int, string>>();
foreach (var th in md.TypeDefinitions)
{
    var t = md.GetTypeDefinition(th);
    var name = md.GetString(t.Name);
    if (name is not ("CardRarity" or "CardType")) continue;
    var map = new Dictionary<int, string>();
    foreach (var fh in t.GetFields())
    {
        var f = md.GetFieldDefinition(fh);
        var c = f.GetDefaultValue();
        if (c.IsNil) continue;
        var blob = md.GetBlobReader(md.GetConstant(c).Value);
        map[blob.Length >= 4 ? blob.ReadInt32() : blob.ReadByte()] = md.GetString(f.Name);
    }
    enums[name] = map;
}

// ---- IL helpers ----------------------------------------------------------
static int OperandSize(ILOpCode op) => op switch
{
    ILOpCode.Ldc_i4_s or ILOpCode.Br_s or ILOpCode.Brfalse_s or ILOpCode.Brtrue_s or ILOpCode.Beq_s
        or ILOpCode.Bge_s or ILOpCode.Bgt_s or ILOpCode.Ble_s or ILOpCode.Blt_s or ILOpCode.Bne_un_s
        or ILOpCode.Bge_un_s or ILOpCode.Bgt_un_s or ILOpCode.Ble_un_s or ILOpCode.Blt_un_s or ILOpCode.Leave_s
        or ILOpCode.Ldarg_s or ILOpCode.Ldarga_s or ILOpCode.Starg_s or ILOpCode.Ldloc_s or ILOpCode.Ldloca_s
        or ILOpCode.Stloc_s or ILOpCode.Unaligned => 1,
    ILOpCode.Ldarg or ILOpCode.Ldarga or ILOpCode.Starg or ILOpCode.Ldloc or ILOpCode.Ldloca or ILOpCode.Stloc => 2,
    ILOpCode.Ldc_i8 or ILOpCode.Ldc_r8 => 8,
    ILOpCode.Switch => -1,
    _ when (int)op is >= 0x00 and <= 0x0E or >= 0x14 and <= 0x1E or >= 0x25 and <= 0x27 or 0x2A
        or >= 0x46 and <= 0x6E or >= 0x76 and <= 0x7B or >= 0x82 and <= 0x8B or >= 0x8E and <= 0x8E
        or >= 0x90 and <= 0xA2 or >= 0xB3 and <= 0xBA or 0xC3 or >= 0xD1 and <= 0xDC or 0xDF or 0xE0
        or >= 0xFE00 and <= 0xFE05 or 0xFE0F or 0xFE11 or 0xFE13 or 0xFE14 or 0xFE17 or 0xFE18 or 0xFE1A
        or 0xFE1D or 0xFE1E => 0,
    _ => 4,
};

IEnumerable<(ILOpCode op, int operand)> Il(MethodDefinitionHandle mh)
{
    var m = md.GetMethodDefinition(mh);
    if (m.RelativeVirtualAddress == 0) yield break;
    var body = pe.GetMethodBody(m.RelativeVirtualAddress);
    var r = body.GetILReader();
    while (r.RemainingBytes > 0)
    {
        int b = r.ReadByte();
        var op = (ILOpCode)(b == 0xFE ? 0xFE00 | r.ReadByte() : b);
        int size = OperandSize(op), operand = 0;
        if (size == -1) { int n = r.ReadInt32(); r.Offset += 4 * n; }
        else if (size == 1) operand = (sbyte)r.ReadByte();
        else if (size == 2) operand = r.ReadInt16();
        else if (size == 4) operand = r.ReadInt32();
        else if (size == 8) r.Offset += 8;
        yield return (op, operand);
    }
}

string MethodName(int token)
{
    var h = MetadataTokens.EntityHandle(token);
    return h.Kind switch
    {
        HandleKind.MethodDefinition => md.GetString(md.GetMethodDefinition((MethodDefinitionHandle)h).Name),
        HandleKind.MemberReference => md.GetString(md.GetMemberReference((MemberReferenceHandle)h).Name),
        _ => "",
    };
}

int? IntConst(ILOpCode op, int operand) => op switch
{
    >= ILOpCode.Ldc_i4_0 and <= ILOpCode.Ldc_i4_8 => (int)op - (int)ILOpCode.Ldc_i4_0,
    ILOpCode.Ldc_i4_m1 => -1,
    ILOpCode.Ldc_i4_s or ILOpCode.Ldc_i4 => operand,
    _ => null,
};

// generic argument names of a MethodSpec token, e.g. ModelDb.Card<Anger>() -> ["Anger"]
List<string> GenericArgs(int token)
{
    var h = MetadataTokens.EntityHandle(token);
    if (h.Kind != HandleKind.MethodSpecification) return new();
    var spec = md.GetMethodSpecification((MethodSpecificationHandle)h);
    var r = md.GetBlobReader(spec.Signature);
    r.ReadByte(); // 0x0A
    int n = r.ReadCompressedInteger();
    var names = new List<string>();
    for (int i = 0; i < n; i++)
    {
        var code = r.ReadSignatureTypeCode();
        if (code is SignatureTypeCode.TypeHandle) names.Add(TypeName(r.ReadTypeHandle()));
        else if ((byte)code is 0x11 or 0x12) names.Add(TypeName(r.ReadTypeHandle())); // class / valuetype
    }
    return names;
}

// ---- 1. card pools: which card types each *CardPool lists -----------------
var cardPool = new Dictionary<string, string>();
foreach (var th in md.TypeDefinitions)
{
    var t = md.GetTypeDefinition(th);
    var name = md.GetString(t.Name);
    if (!TypeNs(t).EndsWith("CardPools") || !name.EndsWith("CardPool")) continue;
    var pool = name[..^"CardPool".Length];
    foreach (var mh in t.GetMethods())
        foreach (var (op, operand) in Il(mh))
            if (op is ILOpCode.Call or ILOpCode.Callvirt)
                foreach (var g in GenericArgs(operand))
                    cardPool.TryAdd(g, pool);
}

// ---- 2. each card's base-constructor constants (cost, type, rarity) -------
var result = new List<Dictionary<string, object?>>();
foreach (var th in md.TypeDefinitions)
{
    var t = md.GetTypeDefinition(th);
    if (!TypeNs(t).EndsWith("Models.Cards")) continue;
    var cls = md.GetString(t.Name);
    if (cls.Contains('<')) continue;
    int? cost = null; string? type = null, rarity = null;
    foreach (var mh in t.GetMethods())
    {
        if (md.GetString(md.GetMethodDefinition(mh).Name) != ".ctor") continue;
        var ints = new List<int>();
        foreach (var (op, operand) in Il(mh))
        {
            if (cls == debugClass)
                Console.Error.WriteLine($"  {op,-12} {(op is ILOpCode.Call or ILOpCode.Callvirt or ILOpCode.Newobj ? MethodName(operand) : operand.ToString())}");
            if (IntConst(op, operand) is int v) ints.Add(v);
            // Only the chained base-constructor call carries the card's identity:
            //   base(int cost, CardType type, CardRarity rarity, TargetType target, ...)
            // Other calls (helpers, field initialisers) also take ints, so they are
            // skipped and their arguments discarded.
            if (op == ILOpCode.Call && MethodName(operand) == ".ctor" && ints.Count >= 3)
            {
                cost = ints[0];
                type = enums.GetValueOrDefault("CardType")?.GetValueOrDefault(ints[1]);
                rarity = enums.GetValueOrDefault("CardRarity")?.GetValueOrDefault(ints[2]);
                break;
            }
            // Calls, field stores (field initialisers like `ldc 13; stfld`) and pops
            // consume the values pushed so far, so they can't be base-ctor args.
            if (op is ILOpCode.Call or ILOpCode.Callvirt or ILOpCode.Newobj or ILOpCode.Stfld
                or ILOpCode.Stsfld or ILOpCode.Pop) ints.Clear();
        }
        if (rarity != null) break;
    }
    result.Add(new()
    {
        ["class"] = cls,
        ["pool"] = cardPool.GetValueOrDefault(cls),
        ["rarity"] = rarity,
        ["card_type"] = type,
        ["energy_cost"] = cost,
    });
}

Console.WriteLine(JsonSerializer.Serialize(new
{
    source = Path.GetFileName(dllPath),
    pools = cardPool.Values.Distinct().OrderBy(p => p),
    enums,
    cards = result.OrderBy(c => (string)c["class"]!),
}, new JsonSerializerOptions { WriteIndented = true }));
